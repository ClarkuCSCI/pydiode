# pydiode

Transfer data through a unidirectional network (i.e., a data diode).

## Installation

First, ensure you have Python version 3.11 or greater.

To install from PyPI:
```
pip install pydiode
```

Or to install from source, clone the repo then run:
```
pip install .
```
**Note:** If local installs are slow, remove large files from the repo (e.g., `build`, `dist`, and `random_data`). When installing, pip makes a copy of everything, so large files slow it down.

To run the GUI, Tk must be installed. For example:
- On macOS:
  - `sudo port install py311-tkinter`
  - `sudo port install tk -x11 +quartz`
- On Linux: `sudo apt install python3.11-tk`

To automatically decrypt PGP-encrypted files:
- On macOS: `sudo port install gnupg2`
- On Linux: `sudo apt install gnupg2`

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

Follow the instructions in `freeze/README.md`

## Citation

If you use this code as part of a publication, please cite [our PEP '23 paper:](https://pep23.com/assets/pdf/pep23-paper7.pdf)

> Peter Story, “Building an Affordable Data Diode to Protect Journalists,” Workshop on Privacy Engineering in Practice (PEP '23), August 2023
