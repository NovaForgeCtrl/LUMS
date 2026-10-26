#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 VERSION COMMIT" >&2
    exit 2
fi

version=$1
commit=$2
if [[ ! "$version" =~ ^[A-Za-z0-9._-]+$ || ! "$commit" =~ ^[A-Fa-f0-9]{7,64}$ ]]; then
    echo "Version or commit contains unsupported characters." >&2
    exit 2
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
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
install -m 0755 "$repo_root/scripts/update-lums.sh" \
    "$package_dir/scripts/update-lums.sh"
install -m 0644 "$repo_root/scripts/update_lums.py" \
    "$package_dir/scripts/update_lums.py"
if [[ -f "$repo_root/scripts/volume_snapshot.py" ]]; then
    install -m 0644 "$repo_root/scripts/volume_snapshot.py" \
        "$package_dir/scripts/volume_snapshot.py"
fi

cat > "$package_dir/README.txt" <<EOF
LUMS update tools
Version: $version
Source commit: $commit

This archive bundles the updater and volume-snapshot helper sources. It is a
download convenience, not a Debian installer and not an automatic production
deployment. Read the matching LUMS installation/update documentation and the
updater's current behavior before using any included tool.

Production updates must not proceed unless the pre-update backup is verified
and application/database rollback has been tested for the target deployment.
EOF

rm -f -- "$archive"
tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 \
    --numeric-owner -czf "$archive" -C "$staging" "$package_name"
(
    cd "$dist_dir"
    sha256sum "$(basename "$archive")" > "$(basename "$archive").sha256"
)
printf 'Created %s\n' "$archive"
