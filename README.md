# pydiode

Transfer data through a unidirectional network (i.e., a data diode).

## Installation

To install from PyPI:
```
pip install pydiode
```

Or to install from source, clone the repo then run:
```
pip install .
```

To run the GUI, Tk must be installed. For example, on macOS:
```
sudo port install py311-tkinter
sudo port install tk -x11 +quartz
```

## GUI Usage

The `pydiode-gui` command will launch the GUI. The GUI can also be run from a frozen executable (see packaging instructions below).

## Command-Line Usage

Documentation:
```
pydiode --help
pydiode send --help
pydiode receive --help
```

Start a receiver on localhost:
```
pydiode --debug receive 127.0.0.1
```

Send data to the receiver, from localhost to localhost:
```
pydiode --debug send 127.0.0.1 127.0.0.1
```

Type some information into the receiver. When finished, press enter, then type Control-D to signal the end-of-file. The receiver should print the received information.

With debug-level logging, you will see details about each packet sent and received. Omit the `--debug` paramater when sending large amount of data, since debug-level logging incurs significant CPU usage.

## Development

### Run Unit Tests

```
python -m unittest discover
```

Since [the unit tests run on the installed code](https://blog.ionelmc.ro/2014/05/25/python-packaging/), remember to install the latest version of the code before running the unit tests.

### Packaging Frozen Executables

First, install PyInstaller:
```
pip install pyinstaller
```

Next, build a frozen executable. On macOS:
```
cd src/pydiode
pyinstaller --windowed --name pydiode gui.py
```

Note that PyInstaller creates a frozen executable for the platform you run it on. For example, when run on macOS, it creates `pydiode.app`.
