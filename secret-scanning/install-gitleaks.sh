#!/usr/bin/env bash
# Install the exact Gitleaks CLI release after verifying its pinned checksum.
set -Eeuo pipefail

readonly version=8.30.1
readonly release_base="https://github.com/gitleaks/gitleaks/releases/download/v${version}"

usage() {
  echo "usage: $0 <destination>" >&2
  exit 2
}

[[ $# == 1 && -n $1 ]] || usage
destination=$1

[[ $(uname -s) == Linux ]] || {
  echo "Gitleaks $version installer supports Linux runners only" >&2
  exit 2
}

case $(uname -m) in
  x86_64)
    archive="gitleaks_${version}_linux_x64.tar.gz"
    checksum=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
    ;;
  aarch64 | arm64)
    archive="gitleaks_${version}_linux_arm64.tar.gz"
    checksum=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080
    ;;
  *)
    echo "unsupported Linux architecture: $(uname -m)" >&2
    exit 2
    ;;
esac

temporary_directory=$(mktemp -d)
archive_path="$temporary_directory/$archive"
cleanup() {
  rm -f -- "$archive_path" "$temporary_directory/gitleaks"
  rmdir -- "$temporary_directory"
}
trap cleanup EXIT

curl \
  --fail \
  --location \
  --proto '=https' \
  --retry 3 \
  --show-error \
  --silent \
  --tlsv1.2 \
  "$release_base/$archive" \
  --output "$archive_path"

if ! printf '%s  %s\n' "$checksum" "$archive_path" |
  sha256sum --check --status --strict; then
  echo "Gitleaks $version archive checksum verification failed" >&2
  exit 1
fi

tar --extract --gzip --file "$archive_path" --directory "$temporary_directory" gitleaks
install -D -m 0755 -- "$temporary_directory/gitleaks" "$destination"

installed_version=$("$destination" version)
[[ $installed_version == "$version" ]] || {
  echo "expected Gitleaks $version, installed $installed_version" >&2
  exit 1
}
echo "installed Gitleaks $version at $destination"
