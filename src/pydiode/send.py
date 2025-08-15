import asyncio
import hashlib
import logging
import math
import os
import stat
import sys
import time

from .common import log_packet, MAX_PAYLOAD, PACKET_HEADER

# Number of EOF packets to send per chunk duration
N_EOF = 4

# Sleep after sending this many packets
PACKET_BURST = 10


class Chunk:
    def __init__(self, data):
        self.data = data
        self.n_packets = math.ceil(len(data) / MAX_PAYLOAD)

    def __iter__(self):
        for i in range(self.n_packets):
            yield self.data[i * MAX_PAYLOAD : ((i + 1) * MAX_PAYLOAD)]


class AsyncReader:
    def __init__(self, chunk_max_data_bytes):
        self.chunk_max_data_bytes = chunk_max_data_bytes
        self.regular_file = stat.S_ISREG(os.fstat(sys.stdin.fileno()).st_mode)
        self.stream_reader = None

    async def read(self):
        """
        Read data asynchronously from STDIN.

        :returns: Bytes read from STDIN
        """
        if self.regular_file:
            # If connected to a regular file, there's no need for a
            # StreamReader: we can quickly read the maximum amount of data for
            # a chunk.
            return await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.buffer.read, self.chunk_max_data_bytes
            )
        else:
            # If STDIN is a pipe or character device, data may become available
            # incrementally. StreamReader lets us read the input incrementally,
            # instead of waiting for a fixed number of bytes to become
            # available.
            # StreamReader doesn't work (and isn't necessary) with file
            # redirection.
            # https://stackoverflow.com/a/71627449
            if not self.stream_reader:
                loop = asyncio.get_event_loop()
                self.stream_reader = asyncio.StreamReader()
                protocol = asyncio.StreamReaderProtocol(self.stream_reader)
                await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
            # Read up to the maximum amount of data in a chunk
            return await self.stream_reader.read(self.chunk_max_data_bytes)


def append_to_chunks(chunks, data, chunk_max_data_bytes):
    """
    Append data to the end of the chunks array, filling chunks that have
    space.

    :param chunks: An array of bytes and bytearrays
    :param data: bytes, to be store in chunks
    :param chunk_max_data_bytes: The maximum number of bytes stored in a chunk.
                                 We assume the data parameter never exceeds
                                 this value.
    """
    # If there are no chunks, or if the last chunk is full
    if (len(chunks) == 0) or (len(chunks[-1]) == chunk_max_data_bytes):
        if len(data) == chunk_max_data_bytes:
            # There's no room for additional data, so immutable suffices
            chunks.append(data)
        else:
            # Append a mutable bytearray, so we can add data later
            chunks.append(bytearray(data))
    # If there is a chunk, and the last chunk has room for data
    else:
        # How much data can fit in the last chunk?
        remaining_space = chunk_max_data_bytes - len(chunks[-1])
        chunks[-1].extend(data[:remaining_space])
        # If some of the data didn't fit in the last chunk
        if remaining_space < len(data):
            chunks.append(bytearray(data[remaining_space:]))


async def read_data(chunks, chunk_max_data_bytes, chunk_duration):
    """
    Read data from STDIN, and store it into the chunks queue.

    :param chunks: An array of bytes and bytearrays
    :param chunk_max_data_bytes: The maximum number of bytes stored in a chunk
    :param chunk_duration: Amount of time taken to send each chunk
    """
    reader = AsyncReader(chunk_max_data_bytes)
    data = await reader.read()
    # Until EOF is encountered
    while data:
        logging.debug(f"Read {len(data)} bytes of data")
        append_to_chunks(chunks, data, chunk_max_data_bytes)
        while len(chunks) > 3:
            # At least the first and second chunks will be full.
            # Wait for chunks to be sent.
            await asyncio.sleep(chunk_duration)
        data = await reader.read()
    # Signal there won't be more data
    chunks.append(None)


class AsyncSleeper:
    def __init__(self, n_sleeps, duration):
        # The number of sleeps we've performed so far
        self.n = 0
        # We will eventually sleep this many times
        self.n_sleeps = n_sleeps
        # Eventually, this much time should pass
        self.duration = duration
        self.start = time.time()

    async def sleep(self):
        self.n += 1
        if self.n > self.n_sleeps:
            raise IndexError(f"Already slept {self.n_sleeps} times")
        # How much time should elapse from start by the end of this sleep?
        target_elapsed = (self.n / self.n_sleeps) * self.duration
        already_elapsed = time.time() - self.start
        sleep_duration = target_elapsed - already_elapsed
        logging.debug(f"Sleeping {sleep_duration:.5f} seconds")
        await asyncio.sleep(sleep_duration)

    async def sleep_remainder(self):
        # If we haven't yet slept for the specified number of times, we will
        # perform one big sleep to fill the remaining time
        if self.n < self.n_sleeps:
            # How much time should elapse from start by the end of this sleep?
            already_elapsed = time.time() - self.start
            sleep_duration = self.duration - already_elapsed
            logging.debug(f"Sleeping remaining {sleep_duration:.5f} seconds")
            await asyncio.sleep(sleep_duration)
            # Record that we have met our "sleep quota"
            self.n = self.n_sleeps


async def _send_eof(chunk_duration, transport, digest):
    logging.debug(f"EOF's digest: {digest.hex()}")
    sleeper = AsyncSleeper(N_EOF, chunk_duration)
    for seq in range(N_EOF):
        header = PACKET_HEADER.pack(b"K", N_EOF, seq)
        data = header + digest
        transport.sendto(data)
        log_packet("Sent", data)
        await sleeper.sleep()


async def _send_chunk(chunk, color, redundancy, chunk_duration, transport):
    start = time.time()
    # Wrap the chunk bytes in a helper class
    c = Chunk(chunk)
    # Sleep after sending this many packets to avoid sending large bursts
    packet_burst = min(c.n_packets, PACKET_BURST)
    # Send the data over the network
    logging.debug(f"{c.n_packets} packets needed to send {color} chunk")
    for r in range(redundancy):
        sleeper = AsyncSleeper(
            math.ceil(c.n_packets / packet_burst), chunk_duration
        )
        logging.debug(f"Send iteration {r + 1}/{redundancy}")
        for seq, payload in enumerate(c):
            header = PACKET_HEADER.pack(color, c.n_packets, seq)
            data = header + payload
            transport.sendto(data)
            log_packet("Sent", data)
            # Sleep after "packet_burst" packets have been sent
            if ((seq + 1) % packet_burst) == 0:
                await sleeper.sleep()
        # Sleep for any remaining time (i.e., if the number of packets isn't a
        # multiple of packet_burst)
        await sleeper.sleep_remainder()
    logging.debug(
        f"Sent {color} chunk of length {len(chunk)} "
        f"in {time.time() - start:.5f} seconds"
    )


class DiodeSendProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_con_lost):
        self.on_con_lost = on_con_lost

    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)


async def send_data(
    chunks, chunk_duration, redundancy, read_ip, write_ip, port
):
    """
    Send chunks over the network.

    :param chunks: An array of bytes and bytearrays
    :param chunk_duration: Amount of time taken to send each chunk
    :param redundancy: How many times to transfer the data
    :param read_ip: Send data to this IP address
    :param write_ip: Send data from this IP address
    :param port: Send data using this port
    """
    # The current chunk color
    color = b"R"

    # Hash of the sent data, for verification by receiver
    sha = hashlib.sha256()

    # Open a UDP "connection"
    loop = asyncio.get_event_loop()
    on_con_lost = loop.create_future()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: DiodeSendProtocol(on_con_lost),
        remote_addr=(read_ip, port),
        # Don't specify the send port: the OS will choose an available port
        local_addr=(write_ip, None),
        allow_broadcast=True,
    )

    # Mitigate early packet loss by sending the first chunk at least 5 times
    warmup = True
    warmup_redundancy = max(5, redundancy)

    # Send data until a None chunk is encountered, indicating EOF
    while True:
        if len(chunks) > 0:
            chunk = chunks.pop(0)
            # There will never be more data
            if chunk is None:
                await _send_eof(chunk_duration, transport, sha.digest())
                break
            # We have a chunk of data to send
            else:
                sha.update(chunk)
                await _send_chunk(
                    chunk,
                    color,
                    redundancy if not warmup else warmup_redundancy,
                    chunk_duration,
                    transport,
                )
                warmup = False
                # Switch the color
                color = b"B" if color == b"R" else b"R"
        # Wait for more data
        else:
            await asyncio.sleep(chunk_duration)

    # Close the UDP "connection"
    transport.close()
    # Wait for the buffer to flush before returning
    await on_con_lost
