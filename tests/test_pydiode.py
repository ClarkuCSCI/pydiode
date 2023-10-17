import hashlib
import os
import socket
import subprocess
import tempfile
import unittest

from pydiode.generator import generate_data
from pydiode.send import append_to_chunks

# Number of bytes in a 1 Mbit
MBIT_BYTES = 125000


class TestIO(unittest.TestCase):
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
        append_to_chunks(chunks, b"!", 10)
        self.assertEqual([b"Not fullHe", b"llo!"], chunks)


class TestSendErrors(unittest.TestCase):
    def test_invalid_ip(self):
        pydiode = subprocess.run(
            ["pydiode", "send", "127.0.0.1", "127.0.0.xxx"], capture_output=True
        )
        self.assertNotEqual(0, pydiode.returncode)
        self.assertEqual(b"", pydiode.stdout)
        self.assertEqual(
            "Can't send from IP address 127.0.0.xxx to 127.0.0.1",
            pydiode.stderr.decode("utf-8").strip(),
        )

    def test_unavailable_ip(self):
        pydiode = subprocess.run(
            ["pydiode", "send", "127.0.0.1", "8.8.8.8"], capture_output=True
        )
        self.assertNotEqual(0, pydiode.returncode)
        self.assertEqual(b"", pydiode.stdout)
        self.assertEqual(
            "Can't send from IP address 8.8.8.8 to 127.0.0.1",
            pydiode.stderr.decode("utf-8").strip(),
        )


class TestReceiveErrors(unittest.TestCase):
    def test_invalid_ip(self):
        pydiode = subprocess.run(
            ["pydiode", "receive", "127.0.0.xxx"], capture_output=True
        )
        self.assertNotEqual(0, pydiode.returncode)
        self.assertEqual(b"", pydiode.stdout)
        self.assertEqual(
            "Can't listen on IP address 127.0.0.xxx",
            pydiode.stderr.decode("utf-8").strip(),
        )

    def test_unavailable_ip(self):
        pydiode = subprocess.run(
            ["pydiode", "receive", "8.8.8.8"], capture_output=True
        )
        self.assertNotEqual(0, pydiode.returncode)
        self.assertEqual(b"", pydiode.stdout)
        self.assertEqual(
            "Can't listen on IP address 8.8.8.8",
            pydiode.stderr.decode("utf-8").strip(),
        )

    def test_allocated_ip(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("127.0.0.1", 1234))
            pydiode = subprocess.run(
                ["pydiode", "receive", "127.0.0.1"], capture_output=True
            )
            self.assertNotEqual(0, pydiode.returncode)
            self.assertEqual(b"", pydiode.stdout)
            self.assertEqual(
                "IP address 127.0.0.1 is already in use",
                pydiode.stderr.decode("utf-8").strip(),
            )
