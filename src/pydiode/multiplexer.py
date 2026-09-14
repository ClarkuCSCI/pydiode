import argparse
import base64
import csv
import logging
import os
import select
import sys

READ_MAX_BYTES = 1000
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
            # TODO Retry connecting if we get a BrokenPipeError
            sys.stdout.flush()
    finally:
        for fd in fd_to_name.keys():
            os.close(fd)


# TODO Create threads for each output pipe, to handle blocking
# TODO Read from STDIN, and place data into buffers for each thread
def demux(pipes):
    # Maps pipe names to their file descriptors, when they are open
    name_to_fd = {}
    # Maps pipe names to their paths
    name_to_path = {os.path.basename(p): p for p in pipes}

    def write(name, data):
        if name in name_to_fd:
            if data:
                os.write(name_to_fd[name], data)
                logging.debug(f"Wrote {len(data)} bytes to {name}")
            else:
                # If EOF was encountered
                os.close(name_to_fd.pop(name))
                logging.debug(f"Closed {name} due to EOF")
        elif name in name_to_path:
            # The pipe must be opened before data can be written
            try:
                name_to_fd[name] = os.open(name_to_path[name], os.O_WRONLY)
                logging.debug(f"Opened {name}")
                write(name, data)
            except FileNotFoundError as e:
                print(e, file=sys.stderr)
        else:
            # Pipe names can be invalid if the input stream is malformed
            logging.warning(f"Invalid pipe: {name[:20]}")

    try:
        reader = csv.DictReader(sys.stdin, fieldnames=["name", "data"])
        for row in reader:
            logging.debug(f"Read row from STDIN")
            write(row["name"], base64.b64decode(row["data"]))
    finally:
        for fd in name_to_fd.values():
            os.close(fd)


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
