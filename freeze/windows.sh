#!/bin/sh

set -ex

# The top-level directory. Use Windows-style file-separators for pyinstaller.
ROOT=`cygpath -w "$PWD"`

# Use pyinstaller to generate the .exe
cd src/pydiode
pyinstaller \
  --noconfirm \
  --windowed \
  --name "Diode Transfer" \
  --icon "$ROOT\freeze\OneWay.png" \
  gui/main.py
cd "$ROOT"
