import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class TestMultiplexer(unittest.TestCase):
    def test_mux_demux(self):
        data = [b"First test", b"Second test"]
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up in and out fifos
            tmppath = Path(tmpdir)
            in_path = tmppath / "in"
            out_path = tmppath / "out"
            in_path.mkdir()
            out_path.mkdir()
            # TODO Use multiple fifos, after multithreading is implemented
            fifos = ["fifo1"]
            in_fifos = [in_path / f for f in fifos]
            out_fifos = [out_path / f for f in fifos]
            for f in in_fifos + out_fifos:
                os.mkfifo(f)
            # Start the muxer and demuxer
            muxer = subprocess.Popen(
                [sys.executable, "-m", "pydiode.multiplexer", "mux"] + in_fifos,
                stdout=subprocess.PIPE,
            )
            demuxer = subprocess.Popen(
                [sys.executable, "-m", "pydiode.multiplexer", "demux"]
                + out_fifos,
                stdin=muxer.stdout,
            )
            # Write data to the in fifos
            for in_fifo, d in zip(in_fifos, data):
                with open(in_fifo, "w") as f:
                    os.write(f.fileno(), d)
            # Read data from the out fifos
            for out_fifo, d in zip(out_fifos, data):
                with open(out_fifo, "rb") as f:
                    self.assertEqual(d, f.read())
            # Terminating the muxer should cause the demuxer to exit
            muxer.terminate()
            muxer.stdout.close()
            muxer.wait()
            demuxer.communicate()
