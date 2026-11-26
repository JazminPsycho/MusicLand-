#!/bin/sh
set -eu
JAPS_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v python3 >/dev/null || { echo 'Falta Python 3.11 o posterior.'; exit 1; }
command -v ffmpeg >/dev/null || { echo 'Instalá FFmpeg: sudo apt install ffmpeg (Debian) o sudo pacman -S ffmpeg (EndeavourOS).'; exit 1; }
if [ ! -x "$JAPS_ROOT/.venv/bin/python" ]; then
 python3 -m venv "$JAPS_ROOT/.venv" || { echo 'Instalá python3-venv.'; exit 1; }
fi
if ! "$JAPS_ROOT/.venv/bin/python" -c "import flask,waitress,PIL" 2>/dev/null; then
 "$JAPS_ROOT/.venv/bin/pip" install -r "$JAPS_ROOT/requirements.txt"
fi
exec "$JAPS_ROOT/.venv/bin/python" "$JAPS_ROOT/server.py" "$@"
