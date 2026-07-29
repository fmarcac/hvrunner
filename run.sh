#!/usr/bin/env bash
set -euo pipefail

launcher_root="$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"
exec python3 "$launcher_root/hvrunner.py" "$@"
