#!/bin/sh

set -ex

ROOT="$PWD"

# Use pyinstaller to generate the one-folder bundle with executable
cd src/pydiode
pyinstaller \
  --noconfirm \
  --name "Diode Transfer" \
  gui/main.py
cd "$ROOT"

# Generate .deb for distribution on Debian-based distros (e.g., Ubuntu, Tails)
# Based on: https://www.pythonguis.com/tutorials/packaging-pyqt5-applications-linux-pyinstaller/

# Create package folders
[ -e package ] && rm -r package
mkdir -p package/opt
mkdir -p package/usr/share/applications
mkdir -p package/usr/share/icons/hicolor/scalable/apps

# Copy files into the package
cp -r "src/pydiode/dist/Diode Transfer" package/opt/diode-transfer
cp freeze/OneWay.svg package/usr/share/icons/hicolor/scalable/apps
cp freeze/diode-transfer.desktop package/usr/share/applications

# Change package permissions
find package/opt/diode-transfer -type f -exec chmod 644 -- {} +
find package/opt/diode-transfer -type d -exec chmod 755 -- {} +
find package/usr/share -type f -exec chmod 644 -- {} +
chmod +x "package/opt/diode-transfer/Diode Transfer"

# Generate the .deb file
fpm --force\
  --chdir package \
  --input-type dir \
  --output-type deb \
  --name diode-transfer \
  --description "Transfer files through a unidirectional network (i.e., a data diode)." \
  --url "https://github.com/ClarkuCSCI/pydiode/" \
  --version 0.0.1 \
  --package diode-transfer.deb

# Move the .deb file alongside PyInstaller's output
mv diode-transfer.deb src/pydiode/dist/
