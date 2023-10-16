# Packaging Frozen Executables

The pydiode's GUI and associated code can be frozen for distribution on macOS, Windows, and Linux. Each of these scripts should be run from the top-level of the repo. Also, each script must be run on the target platform. For example, macOS is required to generate .app files and Windows is required to generate .exe files. Using Docker, any platform can generate .deb files for Debian-based distributions.

All platforms require PyInstaller, which can be installed with:
```
pip install pyinstaller
```

To generate a .app file for macOS, from the top-level of the repo run:
```
./freeze/macOS.sh
```
This will create `src/pydiode/dist/Diode Transfer.app`
