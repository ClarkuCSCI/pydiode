import csv
import hashlib
import logging
import struct
import sys

# How much data will fit in each packet we send?
# Experimentally, these are the maximum UDP payloads I can send on macOS:
# - 1472 for broadcast packets
# - 9216 for non-broadcast packets
# Packets >1472 bytes are fragmented: https://stackoverflow.com/a/15003663/
# macOS can receive broadcast packets of either size.
# For broadcast support, we default to 1472 when running on macOS.
LINUX_UDP_MAX_BYTES = 9216
UDP_MAX_BYTES = 1472 if sys.platform == "darwin" else LINUX_UDP_MAX_BYTES

# Number of bits in a byte
BYTE = 8

# Color, represented as a character: Red, Blue, and blacK (1 byte).
# Number of packets, represented as an unsigned short (2 bytes)
# Sequence number, represented as an unsigned short (2 bytes)
# Payload length, represented as an unsigned short (2 bytes)
# The payload, represented as an array of bytes
PACKET_HEADER = struct.Struct("<cHHH")

# Maximum payload length
MAX_PAYLOAD = UDP_MAX_BYTES - PACKET_HEADER.size

# Whether to log details about each packet sent/received.
# Only log packet details when debugging, due to CPU overhead.
LOG_PACKETS = False


def log_packet(prefix, data):
    if LOG_PACKETS:
        color, n_packets, seq, len_payload = PACKET_HEADER.unpack(
            data[: PACKET_HEADER.size]
        )
        logging.debug(
            f"{prefix} <Packet color={color} n_packets={n_packets} "
            f"seq={seq} len_payload={len_payload}>"
        )


def write_packet_details(filename, packet_details):
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "PacketDigest"])
        writer.writeheader()
        for i, data in enumerate(packet_details):
            writer.writerow(
                {"ID": i, "PacketDigest": hashlib.sha256(data).hexdigest()[:7]}
            )
