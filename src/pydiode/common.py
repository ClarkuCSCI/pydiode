import logging
import struct

# How much data will fit in each packet we send?
# Experimentally, this is the maximum UDP payload I can send on macOS.
UDP_MAX_BYTES = 9216

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
