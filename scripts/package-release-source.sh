#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 RELEASE_TAG" >&2
    exit 2
fi

release_tag=$1
if [[ ! "$release_tag" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$ ]]; then
    echo "Release tag contains unsupported characters." >&2
    exit 2
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
dist_dir="$repo_root/dist"
commit="$(git -C "$repo_root" rev-parse HEAD)"
archive_name="lums-source-$release_tag.tar.gz"
archive="$dist_dir/$archive_name"

mkdir -p "$dist_dir"
git -C "$repo_root" archive \
    --format=tar \
    --prefix="lums-source-$release_tag/" \
    HEAD \
    | gzip -n > "$archive"
printf '%s\n' "$commit" > "$dist_dir/lums-source-$release_tag.commit"
(
    cd "$dist_dir"
    sha256sum "$archive_name" > "$archive_name.sha256"
)
