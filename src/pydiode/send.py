import hashlib
import logging
import math
import os
import select
import socket
import stat
import sys
import time

from .common import log_packet, MAX_PAYLOAD, PACKET_HEADER

# Send the first chunk at least this many times.
# We have observed elevated packet loss into packet index ~330.
MIN_WARMUP_CHUNKS = 5

# Sleep after sending this many packets
PACKET_BURST = 10

# Send the EOF chunk at least this many times
MIN_EOF_CHUNKS = 2


class Chunk:
    """
    Generate packets for this chunk. All packets are fully loaded, with some
    including padding. If the supplied data doesn't completely fill the chunk,
    then the iterator will repeat packets for redundancy.
    """

    def __init__(self, data, color, chunk_max_packets):
        self.data = data
        self.color = color
        self.n_packets = math.ceil(len(data) / MAX_PAYLOAD)
        self.chunk_max_packets = chunk_max_packets

    def __iter__(self):
        for p in range(self.chunk_max_packets):
            i = p % self.n_packets
            payload = self.data[i * MAX_PAYLOAD : ((i + 1) * MAX_PAYLOAD)]
            padding = bytes(MAX_PAYLOAD - len(payload))
            header = PACKET_HEADER.pack(
                self.color, self.n_packets, i, len(payload)
            )
            yield header + payload + padding


class Reader:
    def __init__(self, chunk_max_data_bytes, finished):
        self.chunk_max_data_bytes = chunk_max_data_bytes
        self.regular_file = stat.S_ISREG(os.fstat(sys.stdin.fileno()).st_mode)
        self.finished = finished

    def read(self):
        """
        Read data from STDIN. If possible, read data progressively (e.g., if
        data is arriving through a pipe).

        :returns: Bytes read from STDIN
        """
        if self.regular_file or sys.platform == "win32":
            # If connected to a regular file, there's no need to read data
            # progressively: we can quickly read the maximum amount of data for
            # a chunk. The is our only option on Windows.
            return sys.stdin.buffer.read(self.chunk_max_data_bytes)
        else:
            # If STDIN is a pipe or character device, data may become available
            # incrementally. We will read the input incrementally, instead of
            # waiting for a fixed number of bytes to become available.
            # This isn't necessary with files, and doesn't work on Windows.
            while self.finished.empty():
                r, _, _ = select.select([sys.stdin.fileno()], [], [], 0.1)
                if r:
                    return os.read(
                        sys.stdin.fileno(), self.chunk_max_data_bytes
                    )


def append_to_chunks(chunks, data, chunk_max_data_bytes):
    """
    Append data to the right of the chunks deque, filling chunks that have
    space.

    :param chunks: A deque of chunks (bytes and bytearrays)
    :param data: bytes, to be store in chunks
    :param chunk_max_data_bytes: The maximum number of bytes stored in a chunk.
                                 We assume the data parameter never exceeds
                                 this value.
    """
    # Attempt to access the rightmost chunk
    try:
        right_chunk = chunks.pop()
        # If the rightmost chunk is full
        if len(right_chunk) == chunk_max_data_bytes:
            # Restore the rightmost chunk
            chunks.append(right_chunk)
            # Append the new data as a new chunk
            if len(data) == chunk_max_data_bytes:
                # There's no room for additional data, so immutable suffices
                chunks.append(data)
            else:
                # Append a mutable bytearray, so we can add data later
                chunks.append(bytearray(data))
        # If the rightmost chunk has room for data
        else:
            # How much data can fit in the rightmost chunk?
            remaining_space = chunk_max_data_bytes - len(right_chunk)
            right_chunk.extend(data[:remaining_space])
            chunks.append(right_chunk)
            # If some of the data didn't fit in the last chunk
            if remaining_space < len(data):
                chunks.append(bytearray(data[remaining_space:]))
    # If there was no rightmost chunk
    except IndexError:
        # Append the new data as a new chunk
        if len(data) == chunk_max_data_bytes:
            # There's no room for additional data, so immutable suffices
            chunks.append(data)
        else:
            # Append a mutable bytearray, so we can add data later
            chunks.append(bytearray(data))


def read(chunks, chunk_max_data_bytes, chunk_duration, finished):
    """
    Read data from STDIN, and store it into the chunks deque.

    :param chunks: A deque of chunks (bytes and bytearrays)
    :param chunk_max_data_bytes: The maximum number of bytes stored in a chunk
    :param chunk_duration: Amount of time needed to send each chunk
    :param finished: A queue used to indicate that reading should stop
    """
    reader = Reader(chunk_max_data_bytes, finished)
    data = reader.read()
    # Until EOF is encountered
    while data and finished.empty():
        logging.debug(f"Read {len(data)} bytes of data")
        append_to_chunks(chunks, data, chunk_max_data_bytes)
        while len(chunks) > 10 and finished.empty():
            # At least the first and second chunks will be full.
            # Wait for chunks to be sent.
            time.sleep(chunk_duration)
        data = reader.read()
    # Signal there won't be more data
    chunks.append(None)


class Sleeper:
    def __init__(self, n_packets, duration):
        # The sleep method will be called once for each packet
        self.n_packets = n_packets
        # We actually sleep every PACKET_BURST packets
        self.n_sleeps = math.ceil(n_packets / PACKET_BURST)
        # The number of times the sleep method has been called so far
        self.p = 0
        # The number of actual sleeps we've performed so far
        self.s = 0
        # Eventually, this much time should pass
        self.duration = duration
        self.start = time.time()

    def sleep(self):
        self.p += 1
        if (self.p % PACKET_BURST) == 0:
            self.s += 1
            if self.s > self.n_sleeps:
                raise IndexError(f"Already slept {self.n_sleeps} times")
            # How much time should elapse from start by the end of this sleep?
            target_elapsed = (self.s / self.n_sleeps) * self.duration
            already_elapsed = time.time() - self.start
            sleep_duration = target_elapsed - already_elapsed
            if sleep_duration > 0:
                logging.debug(f"Sleeping {sleep_duration:.5f} seconds")
                time.sleep(sleep_duration)

    def sleep_remainder(self):
        # If we haven't yet slept for the specified number of times, we will
        # perform one big sleep to fill the remaining time
        if self.s < self.n_sleeps:
            # How much time should elapse from start by the end of this sleep?
            already_elapsed = time.time() - self.start
            sleep_duration = self.duration - already_elapsed
            if sleep_duration > 0:
                logging.debug(
                    f"Sleeping remaining {sleep_duration:.5f} seconds"
                )
                time.sleep(sleep_duration)
            # Record that we have met our "sleep quota"
            self.s = self.n_sleeps


class DiodeTransport:
    def __init__(self, sock, read_ip, write_ip, port):
        self.sock = sock
        # Enable broadcast
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Omit the send port: the OS will choose an available port
        sock.bind((write_ip, 0))
        self.read_ip = read_ip
        self.port = port

    def sendto(self, data):
        self.sock.sendto(data, (self.read_ip, self.port))


def _send_chunk(
    chunk,
    packet_details,
    color,
    redundancy,
    chunk_duration,
    chunk_max_packets,
    transport,
):
    """
    Send packets containing all the data in the chunk, possibly redundantly
    until the target number of packets is sent.
    """
    start = time.time()
    # Wrap the chunk bytes in a helper class
    c = Chunk(chunk, color, chunk_max_packets)
    # Send the data over the network
    logging.debug(f"{c.n_packets} packets needed to send {color} chunk")
    for r in range(redundancy):
        sleeper = Sleeper(chunk_max_packets, chunk_duration)
        logging.debug(f"Send iteration {r + 1}/{redundancy}")
        for data in c:
            transport.sendto(data)
            log_packet("Sent", data)
            if (color == b"R" or color == b"B") and packet_details is not None:
                packet_details.append(data)
            sleeper.sleep()
        # Sleep for any remaining time (i.e., if the number of packets isn't a
        # multiple of PACKET_BURST)
        sleeper.sleep_remainder()
    logging.debug(
        f"Sent {color} chunk of length {len(chunk)} "
        f"in {time.time() - start:.5f} seconds"
    )


def send(
    chunks,
    packet_details,
    chunk_duration,
    chunk_max_packets,
    redundancy,
    transport,
):
    """
    Send chunks over the network.

    :param chunks: A deque of chunks (bytes and bytearrays)
    :param packet_details: A list for packet data, or None
    :param chunk_duration: Amount of time needed to send each chunk
    :param chunk_max_packets: Maximum number of packets per chunk
    :param redundancy: How many times to transfer the data
    :param transport: Send data using this wrapper around a UDP socket
    """
    # The current chunk color
    color = b"R"

    # Hash of the sent data, for verification by receiver
    sha = hashlib.sha256()

    # Mitigate early packet loss by sending the first chunk multiple times
    warmup = True
    warmup_redundancy = MIN_WARMUP_CHUNKS + redundancy - 1

    # Send data until a None chunk is encountered, indicating EOF
    prev_chunk = None
    while True:
        try:
            chunk = chunks.popleft()
            prev_chunk = chunk
            # There will never be more data
            if chunk is None:
                digest = sha.digest()
                logging.debug(f"EOF's digest: {digest.hex()}")
                _send_chunk(
                    digest,
                    packet_details,
                    b"K",
                    MIN_EOF_CHUNKS + redundancy - 1,
                    chunk_duration,
                    chunk_max_packets,
                    transport,
                )
                break
            # We have a chunk of data to send
            else:
                sha.update(chunk)
                _send_chunk(
                    chunk,
                    packet_details,
                    color,
                    redundancy if not warmup else warmup_redundancy,
                    chunk_duration,
                    chunk_max_packets,
                    transport,
                )
                warmup = False
                # Switch the color
                color = b"B" if color == b"R" else b"R"
        # If there were no chunks in the deque
        except IndexError:
            # Resend the previous chunk while we wait for more data
            if prev_chunk:
                logging.debug("Resending previous chunk while waiting for data")
                _send_chunk(
                    prev_chunk,
                    packet_details,
                    b"B" if color == b"R" else b"R",  # Previous color
                    1,  # Single redundancy for greater responsiveness
                    chunk_duration,
                    chunk_max_packets,
                    transport,
                )
            # Wait for data
            else:
                logging.debug("Waiting for data")
                time.sleep(chunk_duration)
