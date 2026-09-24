"""
multiplexer.py

Usage notes:
- The muxer will never exit unless it receives a signal (e.g., SIGTERM).
- After the demuxer reads EOF from STDIN, it will exit after it writes all
  buffered data to its output pipes.
- The demuxer will buffer data in memory without limit until another program
  reads from its output pipes.
"""

import argparse
import base64
import binascii
import csv
import logging
import os
import queue
import select
import sys
import threading

# macOS and Linux's default max pipe buffer size is 64 KiB
READ_MAX_BYTES = 2**16
# For responsiveness to signals (e.g., SIGINT)
MAX_WAIT = 0.1

# TODO Currently, we output the data in a CSV format, which increases the size
# of non-text data significantly. There are more efficient options.


def mux(pipes):
    # Maps named pipe file descriptors to their names
    fd_to_name = {}
    try:
        for pipe in pipes:
            try:
                pipe_fd = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
                fd_to_name[pipe_fd] = os.path.basename(pipe)
            except FileNotFoundError as e:
                print(e, file=sys.stderr)
        writer = csv.writer(sys.stdout)
        while True:
            ready, _, _ = select.select(fd_to_name.keys(), [], [], MAX_WAIT)
            for r in ready:
                data = os.read(r, READ_MAX_BYTES)
                logging.debug(f"Read {len(data)} bytes from {fd_to_name[r]}")
                writer.writerow(
                    [
                        fd_to_name[r],
                        base64.b64encode(data).decode("ascii"),
                    ]
                )
                logging.debug(f"Wrote row to STDOUT")
            sys.stdout.flush()
    finally:
        for fd in fd_to_name.keys():
            os.close(fd)


def write(pipe, q):
    fd = None
    data = q.get()
    # If data is None, the thread should join
    # If data is b"", EOF was encountered
    # Otherwise, data should be written out
    while data is not None:
        if fd:
            if data:
                os.write(fd, data)
                logging.debug(f"Wrote {len(data)} bytes to {pipe}")
            else:
                # If EOF was encountered
                os.close(fd)
                fd = None
                logging.debug(f"Closed {pipe} due to EOF")
            data = q.get()
        else:
            # The pipe must be opened before data can be written
            try:
                fd = os.open(pipe, os.O_WRONLY)
                logging.debug(f"Opened {pipe}")
            except FileNotFoundError as e:
                logging.warning(e)
                break
    if fd:
        os.close(fd)


def demux(pipes):
    name_to_queue = {}
    name_to_thread = {}
    for pipe in pipes:
        name = os.path.basename(pipe)
        q = queue.Queue()
        name_to_queue[name] = q
        name_to_thread[name] = threading.Thread(
            target=write,
            args=(
                pipe,
                q,
            ),
        )
        name_to_thread[name].start()

    try:
        reader = csv.DictReader(sys.stdin, fieldnames=["name", "data"])
        for row in reader:
            logging.debug(f"Read row from STDIN")
            if row["name"] in name_to_queue:
                try:
                    name_to_queue[row["name"]].put(
                        base64.b64decode(row["data"])
                    )
                except binascii.Error as e:
                    logging.warning(e)
            else:
                # Pipe names can be invalid if the input stream is malformed
                logging.warning(f"Invalid pipe: {row['name'][:20]}")
    finally:
        for name, q in name_to_queue.items():
            # Threads should be joinable after they encounter None
            q.put(None)
            name_to_thread[name].join()


def main():
    parser = argparse.ArgumentParser(
        description="""
                    Multiplex or demultiplex streams. When multiplexing,
                    multiple input streams are combined into a single output
                    stream. When demultiplexing, a single input stream is
                    separated into multiple output streams.
                    """
    )
    parser.add_argument(
        "mode",
        choices=["mux", "demux"],
        help="Whether to multiplex (mux) or demultiplex (demux)",
    )
    parser.add_argument(
        "pipe",
        help="Paths to named pipes for multiple inputs or outputs",
        nargs="+",
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
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    if len(args.pipe) != len({os.path.basename(p) for p in args.pipe}):
        print("Error: Pipes must have unique names", file=sys.stderr)
        exit(1)

    if args.mode == "mux":
        mux(args.pipe)
    else:
        demux(args.pipe)


if __name__ == "__main__":
    main()
