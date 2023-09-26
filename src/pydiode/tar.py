import argparse
import os
import sys
import tarfile


def main():
    parser = argparse.ArgumentParser(
        description="Create or extract a streamed gzipped tar file"
    )
    subparsers = parser.add_subparsers(
        help="Whether to run in create or extract mode"
    )
    create_parser = subparsers.add_parser("create", help="Create a tar stream")
    create_parser.add_argument(
        "filename",
        help="File to include",
        nargs="+",
    )
    extract_parser = subparsers.add_parser(
        "extract", help="Extract files from a tar stream"
    )
    extract_parser.add_argument(
        "path",
        help="Where to save the extracted files",
    )
    args = parser.parse_args()

    if "filename" in args:
        with tarfile.open(mode="w|gz", fileobj=sys.stdout.buffer) as tar:
            for filename in args.filename:
                tar.add(filename, arcname=os.path.basename(filename))
    elif "path" in args:
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as tar:
            tar.extractall(args.path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
