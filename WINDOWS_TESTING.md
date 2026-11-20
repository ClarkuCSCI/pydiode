# PyDiode native Windows testing and compatibility findings

## Environment and setup

* PyDiode 1.0.0 was found in a Python 3.11 environment, with `pydiode.exe` discoverable from PowerShell.
* GPG decryption tests initially could not launch `gpg`. Temporarily prepending `C:\\Program Files\\GnuPG\\bin` to PowerShell's `PATH` allowed the decryption test to pass. This was a local environment change, not a tracked source-code change.
* Broadcast reception worked after correcting the receiver's IP configuration. This was a network configuration fix, not a tracked source-code change.

## Test changes and findings

|Area|Problem observed|Change or finding|Status|
|-|-|-|-|
|Test module import|`unittest.mock` not explicitly imported while a mock patch decorator was used|Added `import unittest.mock`|Import issue fixed locally|
|File I/O checksum|`shasum -a 256` unavailable in native Windows PowerShell|Replaced external command dependency with Python SHA-256 (`hashlib`)|Individual file I/O test later passed|
|Checksum parsing|Extra Windows `\\r\\n` caused false string mismatch|Normalized/stripped trailing line endings; final uploaded test calculates the hash directly|Individual file I/O test later passed|
|Pipe I/O|Windows `echo` produced bytes differing from expected `b"Hello\\n"`|Supplied exact bytes through `stdin=subprocess.PIPE` and `communicate(input=b"Hello\\n")`|Individual pipe I/O test passed|
|Pipe I/O chunk duration|Input/shell behavior or test setup yielded a mismatch/empty output earlier|Used controlled binary stdin, preserving chunk-duration option|Individual test subsequently passed|
|Packet details|Shell-generated input differed from expected input; output had Windows-style line endings|Used direct `stdin` bytes and normalized `\\r\\n` in the analyzer assertion|Individual packet-details test passed|
|Pipe responsiveness|Receiver waited for `readline()` while sender's stdin remained open|Closing stdin before waiting made the altered test pass|**Unresolved:** closing stdin changes the property tested; original streaming responsiveness needs investigation|
|Multiplexer/demultiplexer|`os.mkfifo()` is unavailable on native Windows|Identified Unix-only test dependency|**Unresolved:** requires Windows-compatible test or supported skip; underlying behavior not established|

Other previously passing tests included bitrate conversion, stuck-process detection, deque operations, chunk handling, and decryption after GPG was made available.

## What the uploaded `test\_pydiode.py` implements

The accompanying test file uses native Python SHA-256, exact binary subprocess input rather than shell `echo`, an explicit `unittest.mock` import, and line-ending normalization for packet analysis. It retains the open-stdin responsiveness test, which may hang on Windows. The complete suite has **not** been verified as passing with this exact final file.

## Follow-up work

1. Run the complete test suite and save full output with test names and tracebacks.
2. Investigate whether data is delivered *before* sender stdin is closed; do not treat a close-before-read test as equivalent.
3. Decide how to exercise multiplexer functionality without Unix `os.mkfifo()` on Windows.
4. Repeat manual file transfer, UDP broadcast, GUI, and performance/tuning checks where appropriate.
5. Add explicit timeouts/cleanup to subprocess and thread tests to avoid indefinite CI hangs.

## Suggested verification commands

From the repository root in PowerShell:

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m unittest tests.test\_pydiode.TestIO.test\_diode\_file\_io -v
python -m unittest tests.test\_pydiode.TestIO.test\_packet\_details -v
```

These are verification commands, not claims that all tests pass.



Additional Windows Compatibility Testing



Fixes completed



Send error handling: Updated pydiode.py to recognize Windows socket errors while preserving the existing Linux and macOS error handling. Both invalid-IP and unavailable-IP send tests passed.



Packet details: Replaced the hardcoded python subprocess command with sys.executable so the analysis runs using the same Python environment as the tests. The test passed with 0.00% packet loss and 0 unordered packets.



Receive error handling: Both invalid-IP and unavailable-IP tests passed.



Allocated UDP port: The test initially encountered a port conflict but passed when rerun.



Other tests: File I/O, pipe I/O, buffering, retransmissions, GUI utilities, and tar tests passed in the individual runs.



Remaining work



Keyboard interrupts: Both send and receive interrupt tests still require Windows compatibility verification. Windows does not support subprocess.send\_signal(signal.SIGINT) in the same way as Unix systems. A Ctrl+Break-based approach is being investigated but has not yet been verified.



Responsiveness and multiplexer: Left unresolved (incompatibility issue) 



