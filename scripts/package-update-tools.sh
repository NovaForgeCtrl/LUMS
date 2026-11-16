#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 VERSION COMMIT" >&2
    exit 2
fi

version=$1
requested_commit=$2

if [[ ! "$version" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$ ]]; then
    echo "Version contains unsupported characters." >&2
    exit 2
fi

if [[ ! "$requested_commit" =~ ^[A-Fa-f0-9]{7,40}$ ]]; then
    echo "Commit must be a valid Git commit hash." >&2
    exit 2
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

head_commit="$(git rev-parse --verify 'HEAD^{commit}')"
resolved_commit="$(git rev-parse --verify "${requested_commit}^{commit}")"

if [[ "$resolved_commit" != "$head_commit" ]]; then
    echo "Refusing to package: requested commit does not match HEAD." >&2
    exit 1
fi

# The packager itself must be tracked, but it is not bundled.
# Do not compare the running packager against HEAD: that would make
# development and testing of this script self-blocking.
if ! git ls-files --error-unmatch \
    scripts/package-update-tools.sh >/dev/null 2>&1; then
    echo "Refusing to package: packager is not tracked by Git." >&2
    exit 1
fi

files=(
    scripts/update-lums.sh
    scripts/update_lums.py
    scripts/release_verification.py
    scripts/release_check.py
    scripts/volume_snapshot.py
)

for file in "${files[@]}"; do
    if [[ ! -f "$file" || -L "$file" ]]; then
        echo "Refusing to package: missing or unsafe source file: $file" >&2
        exit 1
    fi

    if ! git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
        echo "Refusing to package: source file is not tracked: $file" >&2
        exit 1
    fi

    if ! git diff --quiet HEAD -- "$file"; then
        echo "Refusing to package: source differs from HEAD: $file" >&2
        exit 1
    fi
done

dist_dir="$repo_root/dist"
staging="$(mktemp -d)"
package_name="lums-update-tools-$version"
package_dir="$staging/$package_name"
archive="$dist_dir/$package_name.tar.gz"

cleanup() {
    rm -rf -- "$staging"
}
trap cleanup EXIT

mkdir -p "$package_dir/scripts" "$dist_dir"

install -m 0755 scripts/update-lums.sh \
    "$package_dir/scripts/update-lums.sh"
install -m 0644 scripts/update_lums.py \
    "$package_dir/scripts/update_lums.py"
install -m 0644 scripts/release_verification.py \
    "$package_dir/scripts/release_verification.py"
install -m 0644 scripts/release_check.py \
    "$package_dir/scripts/release_check.py"
install -m 0644 scripts/volume_snapshot.py \
    "$package_dir/scripts/volume_snapshot.py"

cat > "$package_dir/README.txt" <<README
LUMS update tools
Version: $version
Source commit: $head_commit

This archive bundles the updater and verification helper sources.
It is a download convenience, not a Debian installer and not an
automatic production deployment.

Production updates must not proceed unless the pre-update backup
is verified and application/database rollback has been tested for
the exact target deployment.
README

rm -f -- "$archive" "$archive.sha256"

tar --sort=name --mtime='UTC 1970-01-01' \
    --owner=0 --group=0 --numeric-owner \
    -czf "$archive" -C "$staging" "$package_name"

(
    cd "$dist_dir"
    sha256sum "$(basename "$archive")" \
        > "$(basename "$archive").sha256"
)

printf 'Created %s\n' "$archive"
printf 'Source commit: %s\n' "$head_commit"
