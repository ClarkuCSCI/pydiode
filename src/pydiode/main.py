import argparse
import asyncio
import logging

import pydiode.common
from .common import BYTE, MAX_PAYLOAD, PACKET_HEADER, UDP_MAX_BYTES
from .send import read_data, send_data
from .receive import AsyncWriter, receive_data


async def async_main():
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
        default=1000000000,
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

        # Calculate chunk_duration based on chunk_max_packets, or vice versa
        if args.chunk_max_packets:
            # How many seconds do we need to send this many fully loaded
            # packets without exceeding max_bitrate?
            args.chunk_duration = (
                args.chunk_max_packets * UDP_MAX_BYTES * BYTE / args.max_bitrate
            )
        else:
            # How many fully loaded packets can be sent per second without
            # exceeding max_bitrate?
            # TODO Consider whether to account for UDP and IPv4 headers.
            args.chunk_max_packets = (
                args.chunk_duration * args.max_bitrate / BYTE / UDP_MAX_BYTES
            )
        logging.debug(f"chunk_max_packets={args.chunk_max_packets}")
        logging.debug(f"chunk_duration={args.chunk_duration}")

        # How much data will fit in these packets?
        chunk_max_data_bytes = int(args.chunk_max_packets * MAX_PAYLOAD)
        logging.debug(f"PACKET_HEADER.size={PACKET_HEADER.size}")
        logging.debug(f"MAX_PAYLOAD={MAX_PAYLOAD}")
        logging.debug(f"chunk_max_data_bytes={chunk_max_data_bytes}")

        # Queue of chunks to be sent
        chunks = []
        # Read and send data concurrently
        await asyncio.gather(
            read_data(chunks, chunk_max_data_bytes, args.chunk_duration),
            send_data(
                chunks,
                args.chunk_duration,
                args.redundancy,
                args.read_ip,
                args.write_ip,
                args.port,
            ),
        )
    # If we are receiving data
    else:
        queue = asyncio.Queue()
        writer = AsyncWriter(queue)
        await asyncio.gather(
            receive_data(queue, args.read_ip, args.port), writer.write()
        )


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
