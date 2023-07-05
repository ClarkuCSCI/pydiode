import argparse
import hashlib
import random


def generate_data(byte_count, seed, output):
    """
    :param byte_count: Number of bytes
    :param seed: Seed used to generate the data
    :param output: Output file name
    :returns: A checksum of the data
    """
    # It's faster to generate data in chunks, instead of one byte at a time
    WRITE_CHUNK = 1000
    random.seed(seed)
    with open(output, "wb") as f:
        for i in range(int(byte_count / WRITE_CHUNK)):
            f.write(random.randbytes(WRITE_CHUNK))
        f.write(random.randbytes(byte_count % WRITE_CHUNK))
    with open(output, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description="Generate a file containing random data."
    )
    parser.add_argument(
        "output",
        help="Output file name",
    )
    parser.add_argument(
        "--byte-count",
        help="Number of bytes to generate",
        type=int,
        default=125000,
    )
    parser.add_argument(
        "--seed",
        help="Random seed for generating data",
        type=int,
        default=random.randint(0, 1000000),
    )
    args = parser.parse_args()
    print(generate_data(args.byte_count, args.seed, args.output))


if __name__ == "__main__":
    main()
