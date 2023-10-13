import os
import subprocess
import sys
import tempfile
import unittest


class TestTar(unittest.TestCase):
    def test_tar_untar(self):
        files = {"1.txt": "ABC", "2.txt": "DEF", "3.txt": "GHI"}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            for file, data in files.items():
                with open(os.path.join(tmpdir, file), "w") as f:
                    f.write(data)
            # Create a destination directory
            dest = os.path.join(tmpdir, "dest")

            # Send test files through a tar stream
            tar_sender = subprocess.Popen(
                [sys.executable, "-m", "pydiode.tar", "create"]
                + [os.path.join(tmpdir, f) for f in files.keys()],
                stdout=subprocess.PIPE,
            )

            # Extract test files from the tar stream
            tar_receiver = subprocess.Popen(
                [sys.executable, "-m", "pydiode.tar", "extract", dest],
                stdin=tar_sender.stdout,
            )

            # Wait for the subprocesses to finish
            tar_receiver.wait(timeout=1)
            tar_sender.wait(timeout=1)
            tar_sender.stdout.close()

            # Ensure the extracted files match the sent files
            for file, data in files.items():
                with open(os.path.join(dest, file), "r") as f:
                    self.assertEqual(data, f.read())

    def test_empty_input(self):
        # For our usage, empty input via STDIN isn't a problem. tar with empty
        # input should exit normally.
        with tempfile.TemporaryDirectory() as tmpdir:
            tar = subprocess.run(
                [sys.executable, "-m", "pydiode.tar", "extract", tmpdir],
                capture_output=True,
                stdin=subprocess.DEVNULL,
            )
            self.assertEqual(0, tar.returncode)
            self.assertEqual(b"", tar.stdout)
            self.assertEqual(b"", tar.stderr)
