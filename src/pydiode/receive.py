import hashlib
import logging
import queue
import sys

from .common import log_packet, LINUX_UDP_MAX_BYTES, PACKET_HEADER


def write(q, r):
    """
    Write data from the queue to STDOUT. Should be run on a separate thread.

    :param q: A thread-safe Queue object for completed chunk data. A None
              object in the queue signals the thread to exit.
    :param r: A thread-safe Queue object for the exit code. The program's exit
              code is non-zero if the received data's digest doesn't match the
              digest in the EOF packet, or if the EOF packet wasn't received.
    """
    sha = hashlib.sha256()
    while True:
        data = q.get()
        if data is None:
            try:
                received_digest = sha.digest()
                eof_digest = q.get(timeout=0.1)
                if received_digest == eof_digest:
                    r.put(0)
                else:
                    logging.warning(
                        "Received data's digest != EOF's digest: "
                        f"{received_digest.hex()} != {eof_digest.hex()}"
                    )
                    r.put(1)
            except queue.Empty:
                logging.info(
                    "Exiting before receiving EOF digest. "
                    f"Received data's digest: {received_digest.hex()}"
                )
                r.put(1)
            finally:
                break
        else:
            sha.update(data)
            sys.stdout.buffer.write(data)


def receive(q, packet_details, sock):
    """
    Receive data from the UDP socket. Store completed chunks on the queue.

    :param q: A thread-safe Queue object for completed chunk data
    :param packet_details: A list for packet data, or None
    :param sock: Receive data from this UDP socket
    """
    # Completed chunks
    completed = {b"R": False, b"B": False}
    # Packets for the chunks
    packets = {b"R": {}, b"B": {}}
    while True:
        data, _ = sock.recvfrom(LINUX_UDP_MAX_BYTES)

        color, n_packets, seq, len_payload = PACKET_HEADER.unpack(
            data[: PACKET_HEADER.size]
        )
        payload_end = PACKET_HEADER.size + len_payload

        log_packet("Received", data)
        if (color == b"R" or color == b"B") and packet_details is not None:
            packet_details.append(data)

        # If EOF (blacK) packet
        if color == b"K":
            # Put None to indicate the transfer is complete
            q.put(None)
            # Put the EOF's payload, a digest of the sent data
            q.put(data[PACKET_HEADER.size : payload_end])
            break
        # Is this packet for an incomplete chunk?
        elif not completed[color]:
            # Record the payload
            packets[color][seq] = data[PACKET_HEADER.size : payload_end]
            # Did we complete the chunk?
            if len(packets[color]) == n_packets:
                logging.debug(f"Packet completed the {color} chunk")
                # Write each packet to STDOUT
                for seq in range(n_packets):
                    q.put(packets[color][seq])
                # Mark this chunk as completed
                completed[color] = True
                packets[color] = {}
                # Mark the other chunk as incomplete
                other_color = b"B" if color == b"R" else b"R"
                completed[other_color] = False
