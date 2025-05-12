import asyncio
import csv
import logging
import struct
import sys
import zlib

# How much data will fit in each packet we send?
# Experimentally, these are the maximum UDP payloads I can send on macOS:
# - 1472 for broadcast packets
# - 9216 for non-broadcast packets
# Packets >1472 bytes are fragmented: https://stackoverflow.com/a/15003663/
# macOS can receive broadcast packets of either size.
# For broadcast support, we default to 1472 when running on macOS.
UDP_MAX_BYTES = 1472 if sys.platform == "darwin" else 9216

# Number of bits in a byte
BYTE = 8

# Color, represented as a character: Red, Blue, and blacK (1 byte).
# Number of packets, represented as an unsigned short (2 bytes)
# Sequence number, represented as an unsigned short (2 bytes)
# The payload, represented as an array of bytes
PACKET_HEADER = struct.Struct("<cHH")

# Maximum payload length
MAX_PAYLOAD = UDP_MAX_BYTES - PACKET_HEADER.size

# Whether to log details about each packet sent/received.
# Only log packet details when debugging, due to CPU overhead.
LOG_PACKETS = False


def log_packet(prefix, data):
    if LOG_PACKETS:
        color, n_packets, seq = PACKET_HEADER.unpack(data[: PACKET_HEADER.size])
        payload_length = len(data) - PACKET_HEADER.size
        logging.debug(
            f"{prefix} <Packet color={color} n_packets={n_packets} "
            f"seq={seq} payload_length={payload_length}>"
        )


class AsyncDumper:
    def __init__(self, queue, packet_details):
        self.queue = queue
        if packet_details:
            self.packet_details = open(packet_details, "w", newline="")
        else:
            self.packet_details = None

    async def write(self):
        """
        Write packet details asynchronously to a .csv file.
        """
        if self.queue:
            writer = csv.DictWriter(
                self.packet_details,
                fieldnames=[
                    "ID",
                    "PayloadDigest",
                ],
            )
            writer.writeheader()
            i = 0
            while True:
                data = await self.queue.get()
                self.queue.task_done()
                if data is None:
                    break
                else:
                    crc32 = zlib.crc32(data)
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        writer.writerow,
                        {
                            "ID": i,
                            "PayloadDigest": crc32,
                        },
                    )
                    i += 1

    def close(self):
        if self.packet_details:
            self.packet_details.close()
