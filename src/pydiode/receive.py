import asyncio
import hashlib
import logging
import queue
import sys

from .common import log_packet, PACKET_HEADER


def write(q):
    """
    Write data from the queue to STDOUT. Should be run on a separate thread.
    """
    sha = hashlib.sha256()
    while True:
        data = q.get()
        if data is None:
            try:
                eof_digest = q.get(timeout=0.1)
                received_digest = sha.digest()
                if received_digest == eof_digest:
                    q.put(0)
                else:
                    logging.warning(
                        "Received data's digest != EOF's digest: "
                        f"{received_digest.hex()} != {eof_digest.hex()}"
                    )
                    q.put(1)
            # If there isn't an EOF digest, receiving exited prematurely
            except queue.Empty:
                q.put(1)
            finally:
                break
        else:
            sha.update(data)
            sys.stdout.buffer.write(data)


class DiodeReceiveProtocol(asyncio.DatagramProtocol):
    def __init__(self, q, packet_details, on_con_lost):
        self.q = q
        self.packet_details = packet_details
        self.on_con_lost = on_con_lost
        # Completed chunks
        self.completed = {b"R": False, b"B": False}
        # Packets for the chunks
        self.packets = {b"R": {}, b"B": {}}

    def datagram_received(self, data, addr):
        color, n_packets, seq, len_payload = PACKET_HEADER.unpack(
            data[: PACKET_HEADER.size]
        )
        payload_end = PACKET_HEADER.size + len_payload

        log_packet("Received", data)
        if (color == b"R" or color == b"B") and self.packet_details is not None:
            self.packet_details.append(data)

        # If EOF (blacK) packet
        if color == b"K":
            # Put None to indicate the transfer is complete
            self.q.put(None)
            # Put the EOF's payload, a digest of the sent data
            self.q.put(data[PACKET_HEADER.size : payload_end])
            self.on_con_lost.set_result(True)
        # Is this packet for an incomplete chunk?
        elif not self.completed[color]:
            # Record the payload
            self.packets[color][seq] = data[PACKET_HEADER.size : payload_end]
            # Did we complete the chunk?
            if len(self.packets[color]) == n_packets:
                logging.debug(f"Packet completed the {color} chunk")
                # Write each packet to STDOUT
                for seq in range(n_packets):
                    self.q.put(self.packets[color][seq])
                # Mark this chunk as completed
                self.completed[color] = True
                self.packets[color] = {}
                # Mark the other chunk as incomplete
                other_color = b"B" if color == b"R" else b"R"
                self.completed[other_color] = False


async def receive_data(q, packet_details, read_ip, port):
    """
    Receive chunks over the network.

    :param q: Store received data onto this queue
    :param packet_details: A list for packet data, or None
    :param read_ip: Listen for data on this IP address
    :param port: Listen for data on this port
    """
    loop = asyncio.get_running_loop()
    on_con_lost = loop.create_future()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DiodeReceiveProtocol(q, packet_details, on_con_lost),
        local_addr=(read_ip, port),
    )
    try:
        await on_con_lost
    finally:
        transport.close()
