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

To run the GUI, Tk must be installed.
- On macOS:
  - `sudo port install py311-tkinter`
  - `sudo port install tk -x11 +quartz`
- On Linux: `sudo apt install python3.11-tk`

### Secure Configuration

The GUI supports using PGP encryption in two ways. First, to encrypt and decrypt all data sent through the GUI. Second, to automatically decrypt PGP-encrypted files (i.e., files ending in .gpg). To use these features, you must install GnuPG.
- On macOS: `sudo port install gnupg2`
- On Linux: `sudo apt install gnupg2`

I recommend reading [the EFF's guide to public key encryption](https://ssd.eff.org/module/deep-dive-end-end-encryption-how-do-public-key-encryption-systems-work) to get familiar with the terminology used by PGP.

PGP's security depends on keeping your secret key secure. Since decryption is performed by the receiving computer, it is best to only store your secret key on that computer. Thus, we suggest generating a key pair on the receiver. It is okay to accept the default options, though you should specify your name.
```
gpg --full-generate-key
```

Next, export your public key. The name specified during key generation (e.g., Peter Story) can be used to identify the key (i.e., the name serves as a key identifier).
```
gpg --armor --export "Peter Story" > story_public.asc
```

Then, copy the public key to the sending computer, and import it:
```
gpg --import story_public.asc
```

In the pydiode GUI, add the key's identifier to the "PGP Key ID" field in the "Settings" tab on the sender and receiver. It is easiest to use your name, assuming you specified it during key generation (e.g., Peter Story). If you also want to automatically decrypt files ending in .gpg, check the "Decrypt received files" checkbox.

Finally, ensure the `gpg` command is on your PATH, so the pydiode GUI can invoke it. On macOS, this can be accomplished [using launchctl:](https://stackoverflow.com/a/70510488/3043071)
```
sudo launchctl config user path /usr/bin:/bin:/usr/sbin:/sbin:/opt/local/bin
```

## GUI Usage

The `pydiode-gui` command will launch the GUI. The GUI can also be run from a frozen executable (see packaging instructions below).

![Diode Transfer's send and receive tabs. The send tab lets you add files to the file transfer queue. The receive tab lets you save files to a directory.](https://datadiode.net/images/software.png)

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

### Speed Up Local Installs

To speed up local installs (i.e., `pip install .`), remove large files from the repo (e.g., `build`, `dist`, and `random_data`). When installing, pip makes a copy of everything, so large files slow it down.

## Citation

If you use this code as part of a publication, please cite [our PEP '23 paper:](https://pep23.com/assets/pdf/pep23-paper7.pdf)

> Peter Story, “Building an Affordable Data Diode to Protect Journalists,” Workshop on Privacy Engineering in Practice (PEP '23), August 2023
