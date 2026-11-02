import hashlib
import logging
import queue
import sys

from .common import log_packet, PACKET_HEADER


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
        chunk = q.get()
        if chunk is None:
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
            # To avoid blocking receive(), we should release the GIL often.
            # The GIL is only released on SHA updates greater than 2047 bytes.
            if len(chunk[0]) > 2047:
                for seq in range(len(chunk)):
                    sha.update(chunk[seq])
                    sys.stdout.buffer.write(chunk[seq])
            # We don't want to join the packets unnecessarily, since it is
            # expensive for large packets.
            else:
                joined = b"".join([chunk[seq] for seq in range(len(chunk))])
                sha.update(joined)
                sys.stdout.buffer.write(joined)
            # For throughput, don't flush after every packet.
            # For responsiveness, flush after every chunk.
            sys.stdout.flush()


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
    # Reuse memory for incoming packets, to reduce memory (de)allocations.
    # IPv4 UDP packet payloads cannot exceed 65507 bytes.
    # Linux and macOS can both receive packets of this size.
    data = bytearray(65507)
    while True:
        n_bytes = sock.recv_into(data)

        color, n_packets, seq, len_payload = PACKET_HEADER.unpack_from(data)
        payload_end = PACKET_HEADER.size + len_payload

        log_packet("Received", data)
        if (color == b"R" or color == b"B") and packet_details is not None:
            packet_details.append(data[:n_bytes])

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
                # Put the chunk's packets in the queue
                q.put(packets[color])
                # Mark this chunk as completed
                completed[color] = True
                packets[color] = {}
                # Mark the other chunk as incomplete
                other_color = b"B" if color == b"R" else b"R"
                completed[other_color] = False
