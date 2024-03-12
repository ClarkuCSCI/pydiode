#!/bin/sh

set -ex

ROOT="$PWD"

# Create icons of various sizes
# Based on: https://stackoverflow.com/a/20703594/3043071
cd freeze
mkdir OneWay.iconset
sips -z 16 16   OneWay.png --out OneWay.iconset/icon_16x16.png
sips -z 32 32   OneWay.png --out OneWay.iconset/icon_16x16@2x.png
sips -z 32 32   OneWay.png --out OneWay.iconset/icon_32x32.png
sips -z 64 64   OneWay.png --out OneWay.iconset/icon_32x32@2x.png
sips -z 128 128 OneWay.png --out OneWay.iconset/icon_128x128.png
sips -z 256 256 OneWay.png --out OneWay.iconset/icon_128x128@2x.png
sips -z 256 256 OneWay.png --out OneWay.iconset/icon_256x256.png
sips -z 512 512 OneWay.png --out OneWay.iconset/icon_256x256@2x.png
sips -z 512 512 OneWay.png --out OneWay.iconset/icon_512x512.png
cp OneWay.png OneWay.iconset/icon_512x512@2x.png
iconutil -c icns OneWay.iconset
rm -R OneWay.iconset
cd "$ROOT"

# Use pyinstaller to generate the .app
cd src/pydiode
pyinstaller \
  --noconfirm \
  --windowed \
  --name "Diode Transfer" \
  --osx-bundle-identifier com.clarku.pydiode \
  --icon "$ROOT/freeze/OneWay.icns" \
  gui/main.py
cd "$ROOT"

# Remove .icns
rm freeze/OneWay.icns
