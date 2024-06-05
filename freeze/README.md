# Packaging Frozen Executables

The pydiode's GUI and associated code can be frozen for distribution on macOS, Windows, and Linux. Each of these scripts should be run from the top-level of the repo. Also, each script must be run on the target platform. For example, macOS is required to generate .app files and Windows is required to generate .exe files. Using Docker, any platform can generate .deb files for Debian-based distributions.

All platforms require PyInstaller, which can be installed with:
```
pip install pyinstaller
```
PyInstaller is installed automatically in Docker.

## macOS

To generate a .app file for macOS, from the top-level of the repo run:
```
./freeze/macOS.sh
```
This will create `src/pydiode/dist/Diode Transfer.app`.

## Linux

To generate a .deb for Linux, from the top-level of the repo run:
```
docker compose up -d --build
docker compose exec python freeze/linux.sh
```
This will create `src/pydiode/dist/diode-transfer.deb`.

You should also copy it into the `diode-instrument` repo:
```
cp src/pydiode/dist/diode-transfer.deb ../diode-instrument/setup/
```

## Windows

Converting from the file icon from `.png` requires installing the Pillow module:
```
pip install Pillow
```

The build should be run within Cygwin, and Cygwin's `PATH` environment variable must be configured so it can locate Python, PyInstaller, and Pillow.

To generate an executable for Windows, from the top-level of the repo run:
```
./freeze/windows.sh
```
This will create `src/pydiode/dist/Diode Transfer.exe`.
