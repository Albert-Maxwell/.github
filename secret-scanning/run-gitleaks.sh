#!/usr/bin/env bash
# Run the pinned organization Gitleaks policy without emitting secret values.
set -Eeuo pipefail

readonly required_version=8.30.1
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
config=${GITLEAKS_CONFIG:-$script_dir/gitleaks.toml}
binary=${GITLEAKS_BIN:-gitleaks}

usage() {
  cat >&2 <<'EOF'
usage: run-gitleaks.sh staged
       run-gitleaks.sh changes <base-sha> <head-sha>
       run-gitleaks.sh history
       run-gitleaks.sh directory

All modes force full redaction and never create a findings report. `history`
scans every reachable commit; it does not modify Git history.
EOF
  exit 2
}

[[ -f $config ]] || {
  echo "gitleaks config not found: $config" >&2
  exit 2
}
command -v "$binary" >/dev/null 2>&1 || {
  echo "gitleaks $required_version is required; see docs/SECRET-SCANNING.md" >&2
  exit 2
}
version=$($binary version 2>&1)
[[ $version == *"$required_version"* ]] || {
  echo "gitleaks $required_version is required, found: $version" >&2
  exit 2
}

mode=${1:-}
case $mode in
  staged)
    [[ $# == 1 ]] || usage
    exec "$binary" git --redact --config "$config" --pre-commit --staged .
    ;;
  changes)
    [[ $# == 3 ]] || usage
    [[ $2 =~ ^[0-9a-f]{40}$ && $3 =~ ^[0-9a-f]{40}$ ]] || {
      echo "base and head must be full lowercase commit SHAs" >&2
      exit 2
    }
    exec "$binary" git --redact --config "$config" --log-opts="$2..$3" .
    ;;
  history)
    [[ $# == 1 ]] || usage
    exec "$binary" git --redact --config "$config" .
    ;;
  directory)
    [[ $# == 1 ]] || usage
    exec "$binary" dir --redact --config "$config" .
    ;;
  *)
    usage
    ;;
esac
