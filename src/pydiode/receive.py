import asyncio
import hashlib
import logging
import sys

from .common import log_packet, PACKET_HEADER


class AsyncWriter:
    def __init__(self, queue, exit_code):
        self.queue = queue
        self.exit_code = exit_code
        # Hash of the received data, used for verification
        self.sha = hashlib.sha256()
        # TODO If connected to a terminal, display output immediately

    async def write(self):
        """
        Write data asynchronously to STDOUT.
        """
        while True:
            data = await self.queue.get()
            self.queue.task_done()
            if data is None:
                eof_digest = await self.queue.get()
                received_digest = self.sha.digest()
                if received_digest == eof_digest:
                    self.exit_code.set_result(0)
                else:
                    logging.warning(
                        "Received data's digest != EOF's digest: "
                        f"{received_digest.hex()} != {eof_digest.hex()}"
                    )
                    self.exit_code.set_result(1)
                break
            else:
                self.sha.update(data)
                await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdout.buffer.write, data
                )


class DiodeReceiveProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue, on_con_lost):
        self.queue = queue
        self.on_con_lost = on_con_lost
        # Completed chunks
        self.completed = {b"R": False, b"B": False}
        # Packets for the chunks
        self.packets = {b"R": {}, b"B": {}}

    def datagram_received(self, data, addr):
        color, n_packets, seq = PACKET_HEADER.unpack(data[: PACKET_HEADER.size])
        log_packet("Received", data)
        # If EOF (blacK) packet
        if color == b"K":
            # Put None to indicate the transfer is complete
            self.queue.put_nowait(None)
            # Put the EOF's payload, a digest of the sent data
            self.queue.put_nowait(data[PACKET_HEADER.size :])
            self.on_con_lost.set_result(True)
        # Is this packet for an incomplete chunk?
        elif not self.completed[color]:
            # Record the payload
            self.packets[color][seq] = data[PACKET_HEADER.size :]
            # Did we complete the chunk?
            if len(self.packets[color]) == n_packets:
                logging.debug(f"Packet completed the {color} chunk")
                # Write each packet to STDOUT
                for seq in range(n_packets):
                    self.queue.put_nowait(self.packets[color][seq])
                # Mark this chunk as completed
                self.completed[color] = True
                self.packets[color] = {}
                # Mark the other chunk as incomplete
                other_color = b"B" if color == b"R" else b"R"
                self.completed[other_color] = False


async def receive_data(queue, read_ip, port):
    """
    Receive chunks over the network.

    :queue: Store received data onto this queue
    :param read_ip: Listen for data on this IP address
    :param port: Listen for data on this port
    """
    loop = asyncio.get_running_loop()
    on_con_lost = loop.create_future()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DiodeReceiveProtocol(queue, on_con_lost),
        local_addr=(read_ip, port),
    )
    try:
        await on_con_lost
    finally:
        transport.close()
