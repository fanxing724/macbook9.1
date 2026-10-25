#!/bin/sh
# Local-only preview. No audio capture, recording file, or network output.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 "$script_dir/camera-preview.py" "$@"
