import argparse
from collections import deque
import logging
import queue
import socket
import sys
import threading

import pydiode.common
from .common import (
    BYTE,
    MAX_PAYLOAD,
    PACKET_HEADER,
    UDP_MAX_BYTES,
    write_packet_details,
)
from .send import DiodeTransport, read, send
from .receive import receive, write


class ChunkConfig:
    """
    Calculates and stores:
    - chunk_max_packets
    - chunk_duration
    - chunk_max_data_bytes

    Note: We don't account for UDP and IPv4 headers, so our actual maximum
    bitrate could be slightly higher than our target.
    """

    def __init__(self, chunk_max_packets, chunk_duration, max_bitrate):
        """
        max_bitrate is required, and either chunk_max_packets or
        chunk_duration should be non-null.
        """
        # Calculate chunk_duration based on chunk_max_packets
        if chunk_max_packets:
            # How many seconds do we need to send this many fully loaded
            # packets without exceeding max_bitrate?
            self.chunk_max_packets = chunk_max_packets
            self.chunk_duration = (
                chunk_max_packets * UDP_MAX_BYTES * BYTE / max_bitrate
            )
        # Calculate chunk_max_packets based on chunk_duration
        else:
            # How many fully loaded packets can be sent per second without
            # exceeding max_bitrate?
            self.chunk_duration = chunk_duration
            self.chunk_max_packets = int(
                chunk_duration * max_bitrate / BYTE / UDP_MAX_BYTES
            )
        # How much data will fit in this chunk?
        self.chunk_max_data_bytes = self.chunk_max_packets * MAX_PAYLOAD


def main():
    parser = argparse.ArgumentParser(
        description="Send and receive data through a data diode via UDP."
    )
    subparsers = parser.add_subparsers(
        help="Whether to run in send or receive mode"
    )
    parser.add_argument(
        "--debug",
        help="Print DEBUG logging",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "--verbose",
        help="Print INFO logging",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    parser.add_argument(
        "--packet-details",
        type=str,
        help="Write packet details into the specified .csv",
    )

    send_parser = subparsers.add_parser("send", help="Send data")
    send_parser.add_argument(
        "read_ip", help="The IP of the interface data is read from"
    )
    send_parser.add_argument(
        "write_ip",
        help="The IP of the interface data is written to",
    )
    send_parser.add_argument(
        "--port",
        type=int,
        help="Send and receive data using this port",
        default=1234,
    )
    send_parser.add_argument(
        "--max-bitrate",
        type=int,
        help="Maximum number of bits transferred per second",
        default=100000000,
    )
    send_parser.add_argument(
        "--chunk-duration",
        type=float,
        help="Send each chunk for this many seconds",
    )
    send_parser.add_argument(
        "--chunk-max-packets",
        type=int,
        help="The maximum number of packets a chunk should contain",
    )
    send_parser.add_argument(
        "--redundancy",
        type=int,
        help="How many times to send each chunk",
        default=2,
    )

    receive_parser = subparsers.add_parser("receive", help="Receive data")
    receive_parser.add_argument(
        "read_ip", help="The IP of the interface data is read from"
    )
    receive_parser.add_argument(
        "--port",
        type=int,
        help="Send and receive data using this port",
        default=1234,
    )

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)
    # Only log packet details when debugging, due to CPU overhead
    if args.loglevel == logging.DEBUG:
        pydiode.common.LOG_PACKETS = True

    # If we are sending data
    if "write_ip" in args:
        if args.chunk_duration and args.chunk_max_packets:
            raise ValueError(
                "Supply either --chunk-duration or --chunk-max-packets"
            )
        elif not args.chunk_duration and not args.chunk_max_packets:
            args.chunk_max_packets = 100

        cc = ChunkConfig(
            args.chunk_max_packets, args.chunk_duration, args.max_bitrate
        )
        logging.debug(f"chunk_max_packets={cc.chunk_max_packets}")
        logging.debug(f"chunk_duration={cc.chunk_duration}")
        logging.debug(f"PACKET_HEADER.size={PACKET_HEADER.size}")
        logging.debug(f"MAX_PAYLOAD={MAX_PAYLOAD}")
        logging.debug(f"chunk_max_data_bytes={cc.chunk_max_data_bytes}")

        try:
            # Deque of chunks to be sent
            chunks = deque()
            # To indicate that reading should stop
            f = queue.Queue()
            packet_details = [] if args.packet_details else None
            # Read from STDIN using a separate thread
            t = threading.Thread(
                target=read,
                args=(chunks, cc.chunk_max_data_bytes, cc.chunk_duration, f),
            )
            # Initialize a socket for sending data
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                transport = DiodeTransport(
                    sock, args.read_ip, args.write_ip, args.port
                )
                # Start the thread if the socket was successfully initialized
                t.start()
                # Send data over the network using the main thread
                send(
                    chunks,
                    packet_details,
                    cc.chunk_duration,
                    cc.chunk_max_packets,
                    args.redundancy,
                    transport,
                )
            if args.packet_details:
                write_packet_details(args.packet_details, packet_details)
            exit_code = 0
        # Don't print the full stack trace for known error types
        except OSError as e:
            if str(e) in {
                # macOS
                "[Errno 49] Can't assign requested address",
                "[Errno 8] nodename nor servname provided, or not known",
                # Linux
                "[Errno 99] Cannot assign requested address",
                "[Errno -2] Name or service not known",
            }:
                print(
                    f"Can't send from IP address",
                    args.write_ip,
                    "to",
                    args.read_ip,
                    file=sys.stderr,
                )
                exit_code = 1
            else:
                raise e
        finally:
            # Indicate that reading should stop
            f.put(True)
            # If the thread was started, wait for it to terminate
            if t.is_alive():
                t.join()
        sys.exit(exit_code)

    # If we are receiving data
    elif "read_ip" in args:
        try:
            # Queue of chunks received
            q = queue.Queue()
            # For the receiver's exit code
            r = queue.Queue()
            packet_details = [] if args.packet_details else None
            # Write to STDOUT using a separate thread
            t = threading.Thread(target=write, args=(q, r))
            t.start()
            # Receive from the network using the main thread
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind((args.read_ip, args.port))
                receive(q, packet_details, sock)
            if args.packet_details:
                write_packet_details(args.packet_details, packet_details)
        # Don't print the full stack trace for known error types
        except OSError as e:
            if str(e) in {
                # macOS
                "[Errno 49] Can't assign requested address",
                "[Errno 8] nodename nor servname provided, or not known",
                # Linux
                "[Errno 99] Cannot assign requested address",
                "[Errno -2] Name or service not known",
                # Windows
                "[Errno 11001] getaddrinfo failed",
                "[WinError 10049] The requested address is not valid in its context",
            }:
                print(
                    f"Can't listen on IP address {args.read_ip}",
                    file=sys.stderr,
                )
            elif str(e) in {
                # macOS
                "[Errno 48] Address already in use",
                # Linux
                "[Errno 98] Address already in use",
                # Windows
                "[WinError 10048] Only one usage of each socket address (protocol/network address/port) is normally permitted",
            }:
                print(
                    f"IP address {args.read_ip} is already in use",
                    file=sys.stderr,
                )
            else:
                raise e
        finally:
            q.put(None)
            t.join()
        # Use the receiver's exit code, unless an exception propagates
        sys.exit(r.get())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
