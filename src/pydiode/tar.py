import argparse
import os
import sys
import tarfile


def main():
    parser = argparse.ArgumentParser(
        description="""
                    Create or extract a streamed tar file. To minimize the
                    attack surface, compression is not used.
                    """
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
        with tarfile.open(mode="w|", fileobj=sys.stdout.buffer) as tar:
            for filename in args.filename:
                tar.add(filename, arcname=os.path.basename(filename))
    elif "path" in args:
        try:
            with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as tar:
                tar.extractall(args.path)
                # Print the path of each file extracted
                for name in tar.getnames():
                    print(os.path.join(args.path, name))
        # Don't print the full stack trace for known error types
        except tarfile.ReadError as e:
            if str(e) == "empty file":
                # Empty input isn't a problem, so we should exit normally.
                # This can happen when pydiode's STDOUT is connected to tar's
                # STDIN, and pydiode exits without output.
                sys.exit(0)
            elif str(e) == "truncated header":
                print(
                    "Invalid header. Did you send a test packet?",
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                print(str(e), file=sys.stderr)
                sys.exit(1)
        # If you attempt to write to a directory without write access
        except PermissionError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        # If you attempt to write to a read-only file system
        except OSError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
