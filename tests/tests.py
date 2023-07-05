import hashlib
import os
import subprocess
import tempfile
import unittest

from pydiode.generator import generate_data
from pydiode.send import append_to_chunks

# Number of bytes in a 1 Mbit
MBIT_BYTES = 125000


class TestPyDiode(unittest.TestCase):
    def test_diode_file_io(self):
        with tempfile.TemporaryDirectory() as tempdir:
            RANDOM_DATA = os.path.join(tempdir, "random_data")
            # Generate 1Mbit of random data
            expected_checksum = generate_data(MBIT_BYTES, 42, RANDOM_DATA)
            # Send the data through localhost
            receive = subprocess.Popen(
                f"pydiode receive 127.0.0.1",
                stdout=subprocess.PIPE,
                shell=True,
            )
            checksum = subprocess.Popen(
                "shasum -a 256",
                stdin=receive.stdout,
                stdout=subprocess.PIPE,
                shell=True,
            )
            send = subprocess.Popen(
                f"pydiode send 127.0.0.1 127.0.0.1 < {RANDOM_DATA}",
                shell=True,
            )
            send.communicate()
            receive.communicate()
            checksum_stdout, _ = checksum.communicate()
            actual_checksum = checksum_stdout.decode("utf-8").split(" ")[0]
            # Check whether the received data matches the sent data
            self.assertEqual(expected_checksum, actual_checksum)

    def test_diode_pipe_io(self):
        expected_hasher = hashlib.sha256()
        expected_hasher.update(b"Hello\n")
        # Send "Hello" through localhost
        receive = subprocess.Popen(
            f"pydiode receive 127.0.0.1",
            stdout=subprocess.PIPE,
            shell=True,
        )
        send = subprocess.Popen(
            "echo Hello | pydiode send 127.0.0.1 127.0.0.1",
            shell=True,
        )
        send.communicate()
        receive_stdout, _ = receive.communicate()
        actual_hasher = hashlib.sha256()
        actual_hasher.update(receive_stdout)
        # Check whether the received data matches the sent data
        self.assertEqual(expected_hasher.hexdigest(), actual_hasher.hexdigest())


class TestChunks(unittest.TestCase):
    def test_empty_chunks(self):
        chunks = []
        append_to_chunks(chunks, b"Hello", 10)
        self.assertEqual([b"Hello"], chunks)

    def test_full_chunks(self):
        chunks = []
        append_to_chunks(chunks, b"I am full!", 10)
        self.assertEqual([b"I am full!"], chunks)
        append_to_chunks(chunks, b"Hello", 10)
        self.assertEqual([b"I am full!", b"Hello"], chunks)

    def test_partial_chunks(self):
        chunks = []
        append_to_chunks(chunks, b"Not full", 10)
        self.assertEqual([b"Not full"], chunks)
        append_to_chunks(chunks, b"Hello", 10)
        self.assertEqual([b"Not fullHe", b"llo"], chunks)
