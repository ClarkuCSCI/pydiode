import csv
import hashlib
import logging
import struct
import sys

# Number of bits in a byte
BYTE = 8

# Color, represented as a character: Red, Blue, and blacK (1 byte).
# Number of packets, represented as an unsigned short (2 bytes)
# Sequence number, represented as an unsigned short (2 bytes)
# Payload length, represented as an unsigned short (2 bytes)
# The payload, represented as an array of bytes
PACKET_HEADER = struct.Struct("<cHHH")

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
                {"ID": i, "PacketDigest": hashlib.sha256(data).hexdigest()[:16]}
            )
