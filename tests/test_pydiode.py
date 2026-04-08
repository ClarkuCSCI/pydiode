from collections import deque
import hashlib
import os
import signal
import socket
import subprocess
import tempfile
import threading
import time
import unittest

from pydiode.generator import generate_data
from pydiode.send import append_to_chunks, BoundedDeque

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
                "sha256sum",
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

    def test_diode_pipe_io_chunk_duration(self):
        expected_hasher = hashlib.sha256()
        expected_hasher.update(b"Hello\n")
        # Send "Hello" through localhost
        receive = subprocess.Popen(
            f"pydiode receive 127.0.0.1",
            stdout=subprocess.PIPE,
            shell=True,
        )
        send = subprocess.Popen(
            (
                "echo Hello | "
                "pydiode send --chunk-duration 0.01 127.0.0.1 127.0.0.1"
            ),
            shell=True,
        )
        send.communicate()
        receive_stdout, _ = receive.communicate()
        actual_hasher = hashlib.sha256()
        actual_hasher.update(receive_stdout)
        # Check whether the received data matches the sent data
        self.assertEqual(expected_hasher.hexdigest(), actual_hasher.hexdigest())

    def test_diode_pipe_io_responsiveness(self):
        receive = subprocess.Popen(
            f"pydiode receive 127.0.0.1",
            stdout=subprocess.PIPE,
            shell=True,
        )
        send = subprocess.Popen(
            "pydiode send 127.0.0.1 127.0.0.1",
            stdin=subprocess.PIPE,
            shell=True,
        )
        send.stdin.write(b"Hello\n")
        send.stdin.flush()
        self.assertEqual(b"Hello\n", receive.stdout.readline())
        send.stdin.close()
        send.wait()
        receive.communicate()

    def test_packet_details(self):
        with tempfile.TemporaryDirectory() as tempdir:
            TX_DETAILS = os.path.join(tempdir, "tx.csv")
            RX_DETAILS = os.path.join(tempdir, "rx.csv")
            ANALYSIS = os.path.join(tempdir, "analysis.csv")
            expected_hasher = hashlib.sha256()
            expected_hasher.update(b"Hello\n")
            # Send "Hello" through localhost
            receive = subprocess.Popen(
                f"pydiode --packet-details {RX_DETAILS} receive 127.0.0.1",
                stdout=subprocess.PIPE,
                shell=True,
            )
            send = subprocess.Popen(
                (
                    "echo Hello | "
                    f"pydiode --packet-details {TX_DETAILS} "
                    "send 127.0.0.1 127.0.0.1"
                ),
                shell=True,
            )
            send.communicate()
            receive_stdout, _ = receive.communicate()
            actual_hasher = hashlib.sha256()
            actual_hasher.update(receive_stdout)
            # Check whether the received data matches the sent data
            self.assertEqual(
                expected_hasher.hexdigest(), actual_hasher.hexdigest()
            )
            # Ensure the details .csv files exist
            self.assertTrue(os.path.exists(TX_DETAILS))
            self.assertTrue(os.path.exists(RX_DETAILS))
            # Try analyzing rx.csv and tx.csv
            analysis = subprocess.run(
                [
                    "python",
                    "-m",
                    "pydiode.analyze_details",
                    TX_DETAILS,
                    RX_DETAILS,
                    ANALYSIS,
                ],
                capture_output=True,
            )
            self.assertEqual(
                analysis.stdout.decode(),
                "0.00% packet loss\n0 unordered packets\n",
            )
            # Ensure the analysis .csv file exists
            self.assertTrue(os.path.exists(ANALYSIS))


class TestBoundedDeque(unittest.TestCase):
    def test_basic_operations(self):
        bd = BoundedDeque(3)
        bd.append("a")
        bd.append("b")
        bd.append("c")
        self.assertEqual(bd.popleft(), "a")
        self.assertEqual(bd.pop(), "c")
        self.assertEqual(bd.popleft(), "b")

    def test_pop_raises(self):
        bd = BoundedDeque(3)
        with self.assertRaises(IndexError):
            bd.pop()

    def test_popleft_raises(self):
        bd = BoundedDeque(3)
        with self.assertRaises(IndexError):
            bd.popleft()

    def test_pop_blocks(self):
        bd = BoundedDeque(3)
        result = []

        def pop_target():
            result.append(bd.pop(wait=True))

        # Popping from an empty deque should block when wait=True
        t = threading.Thread(target=pop_target)
        t.start()
        time.sleep(0.1)
        self.assertEqual([], result)
        # Popping should work after an item is appended
        bd.append("a")
        t.join(timeout=1)
        self.assertEqual(["a"], result)

    def test_popleft_blocks(self):
        bd = BoundedDeque(3)
        result = []

        def pop_target():
            result.append(bd.popleft(wait=True))

        # Left-popping from an empty deque should block when wait=True
        t = threading.Thread(target=pop_target)
        t.start()
        time.sleep(0.1)
        self.assertEqual([], result)
        # Left-popping should work after an item is appended
        bd.append("a")
        t.join(timeout=1)
        self.assertEqual(["a"], result)

    def test_append_blocks(self):
        bd = BoundedDeque(1)
        bd.append("a")
        appended = threading.Event()

        def append_target():
            bd.append("b")
            appended.set()

        # Appending to a full deque should block
        t = threading.Thread(target=append_target)
        t.start()
        time.sleep(0.1)
        self.assertFalse(appended.is_set())
        # Appending should work after an item is popped
        self.assertEqual("a", bd.pop())
        appended.wait(timeout=1)
        self.assertTrue(appended.is_set())


class TestChunks(unittest.TestCase):
    def test_empty_chunks(self):
        chunks = BoundedDeque(3)
        append_to_chunks(chunks, b"Hello", 10)
        self.assertEqual(deque([b"Hello"]), chunks.deque)

    def test_full_chunks(self):
        chunks = BoundedDeque(3)
        append_to_chunks(chunks, b"I am full!", 10)
        self.assertEqual(deque([b"I am full!"]), chunks.deque)
        append_to_chunks(chunks, b"Hello", 10)
        self.assertEqual(deque([b"I am full!", b"Hello"]), chunks.deque)

    def test_partial_chunks(self):
        chunks = BoundedDeque(3)
        append_to_chunks(chunks, b"Not full", 10)
        self.assertEqual(deque([b"Not full"]), chunks.deque)
        append_to_chunks(chunks, b"Hello", 10)
        self.assertEqual(deque([b"Not fullHe", b"llo"]), chunks.deque)
        append_to_chunks(chunks, b"!", 10)
        self.assertEqual(deque([b"Not fullHe", b"llo!"]), chunks.deque)


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


class TestKeyboardInterrupt(unittest.TestCase):
    def test_interrupt_send(self):
        send = subprocess.Popen(
            ["pydiode", "send", "127.0.0.1", "127.0.0.1"],
            stderr=subprocess.PIPE,
        )
        time.sleep(0.1)
        send.send_signal(signal.SIGINT)
        _, stderr = send.communicate()
        self.assertIn(b"KeyboardInterrupt", stderr)

    def test_interrupt_receive(self):
        receive = subprocess.Popen(
            ["pydiode", "receive", "127.0.0.1"],
            stderr=subprocess.PIPE,
        )
        time.sleep(0.1)
        receive.send_signal(signal.SIGINT)
        _, stderr = receive.communicate()
        self.assertIn(b"KeyboardInterrupt", stderr)


class TestRetransmits(unittest.TestCase):
    @unittest.mock.patch("pydiode.send._send_chunk")
    def test_send_retransmits(self, mock_send_chunk):
        from pydiode.send import send, _send_chunk

        chunks = BoundedDeque(3)
        chunks.append(b"Hello")
        t = threading.Thread(
            target=lambda: send(chunks, None, 0.01, 10, 2, None)
        )
        t.start()
        time.sleep(0.01)
        chunks.append(None)
        chunks.append(b"fakedigest")
        t.join()
        self.assertGreater(mock_send_chunk.call_count, 2)
