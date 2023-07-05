# PyDiode

Transfer data through a unidirectional network (i.e., a data diode).

## Installation

Install from PyPI:
```
pip install pydiode
```

To install from source, clone the repo then run:
```
pip install .
```

## Usage

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

Run unit tests:
```
python -m unittest tests.tests
```

Since [the unit tests run on the installed code](https://blog.ionelmc.ro/2014/05/25/python-packaging/), remember to install the latest version of the code before running the unit tests.
