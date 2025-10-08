import asyncio
import hashlib
import logging
import math
import os
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


async def read_data(chunks, chunk_config):
    """
    Read data from STDIN, and store it into the chunks queue.

    :param chunks: An array of bytes and bytearrays
    :param chunk_config: Contains the maximum number of bytes stored in a chunk
                         and the amount of time needed to send each chunk
    """
    reader = AsyncReader(chunk_config.chunk_max_data_bytes)
    data = await reader.read()
    # Until EOF is encountered
    while data:
        logging.debug(f"Read {len(data)} bytes of data")
        append_to_chunks(chunks, data, chunk_config.chunk_max_data_bytes)
        while len(chunks) > 3:
            # At least the first and second chunks will be full.
            # Wait for chunks to be sent.
            await asyncio.sleep(chunk_config.chunk_duration)
        data = await reader.read()
    # Signal there won't be more data
    chunks.append(None)


class AsyncSleeper:
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

    async def sleep(self):
        self.p += 1
        if (self.p % PACKET_BURST) == 0:
            self.s += 1
            if self.s > self.n_sleeps:
                raise IndexError(f"Already slept {self.n_sleeps} times")
            # How much time should elapse from start by the end of this sleep?
            target_elapsed = (self.s / self.n_sleeps) * self.duration
            already_elapsed = time.time() - self.start
            sleep_duration = target_elapsed - already_elapsed
            # Don't let the reader interrupt us if we are running behind
            if sleep_duration > 0:
                logging.debug(f"Sleeping {sleep_duration:.5f} seconds")
                await asyncio.sleep(sleep_duration)

    async def sleep_remainder(self):
        # If we haven't yet slept for the specified number of times, we will
        # perform one big sleep to fill the remaining time
        if self.s < self.n_sleeps:
            # How much time should elapse from start by the end of this sleep?
            already_elapsed = time.time() - self.start
            sleep_duration = self.duration - already_elapsed
            # Don't let the reader interrupt us if we are running behind
            if sleep_duration > 0:
                logging.debug(
                    f"Sleeping remaining {sleep_duration:.5f} seconds"
                )
                await asyncio.sleep(sleep_duration)
            # Record that we have met our "sleep quota"
            self.s = self.n_sleeps


async def _send_chunk(
    chunk,
    packet_details,
    color,
    redundancy,
    chunk_config,
    transport,
):
    """
    Send packets containing all the data in the chunk, possibly redundantly
    until the target number of packets is sent.
    """
    start = time.time()
    # Wrap the chunk bytes in a helper class
    c = Chunk(chunk, color, chunk_config.chunk_max_packets)
    # Send the data over the network
    logging.debug(f"{c.n_packets} packets needed to send {color} chunk")
    for r in range(redundancy):
        sleeper = AsyncSleeper(
            chunk_config.chunk_max_packets, chunk_config.chunk_duration
        )
        logging.debug(f"Send iteration {r + 1}/{redundancy}")
        for data in c:
            transport.sendto(data)
            log_packet("Sent", data)
            if (color == b"R" or color == b"B") and packet_details is not None:
                packet_details.append(data)
            await sleeper.sleep()
        # Sleep for any remaining time (i.e., if the number of packets isn't a
        # multiple of PACKET_BURST)
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
    chunks, packet_details, chunk_config, redundancy, read_ip, write_ip, port
):
    """
    Send chunks over the network.

    :param chunks: A list for bytes and bytearrays
    :param packet_details: A list for packet data, or None
    :param chunk_config: Contains the amount of time needed to send each chunk
                         as well as the maximum number of packets per chunk
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

    # Mitigate early packet loss by sending the first chunk multiple times
    warmup = True
    warmup_redundancy = MIN_WARMUP_CHUNKS + redundancy - 1

    # Send data until a None chunk is encountered, indicating EOF
    prev_chunk = None
    while True:
        # Give the reader a chance to read chunks
        await asyncio.sleep(0)
        if len(chunks) > 0:
            chunk = chunks.pop(0)
            prev_chunk = chunk
            # There will never be more data
            if chunk is None:
                digest = sha.digest()
                logging.debug(f"EOF's digest: {digest.hex()}")
                await _send_chunk(
                    digest,
                    packet_details,
                    b"K",
                    max(MIN_EOF_CHUNKS, redundancy),
                    chunk_config,
                    transport,
                )
                break
            # We have a chunk of data to send
            else:
                sha.update(chunk)
                await _send_chunk(
                    chunk,
                    packet_details,
                    color,
                    redundancy if not warmup else warmup_redundancy,
                    chunk_config,
                    transport,
                )
                warmup = False
                # Switch the color
                color = b"B" if color == b"R" else b"R"
        # Resend the previous chunk while we wait for more data
        elif prev_chunk:
            logging.debug("Resending previous chunk while waiting for data")
            await _send_chunk(
                prev_chunk,
                packet_details,
                b"B" if color == b"R" else b"R",  # Previous color
                1,  # Single redundancy for greater responsiveness
                chunk_config,
                transport,
            )
        # Send a chunk of white packets while we wait for data
        else:
            logging.debug("Sending white chunk while waiting for data")
            await _send_chunk(
                bytes(1),
                packet_details,
                b"W",  # Previous color
                1,  # Single redundancy for greater responsiveness
                chunk_config,
                transport,
            )

    # Close the UDP "connection"
    transport.close()
    # Wait for the buffer to flush before returning
    await on_con_lost
