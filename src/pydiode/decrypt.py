"""
decrypt.py

Reads filenames from STDIN, and uses gpg to decrypt files ending in .gpg

Usage:
> ls
1.txt.gpg
> echo "1.txt.gpg" | python -m pydiode.decrypt
> ls
1.txt
1.txt.gpg
"""

from pathlib import Path
import subprocess
import sys


def main():
    for line in sys.stdin:
        path = Path(line.strip())
        if path.exists() and path.suffix == ".gpg":
            subprocess.run(
                [
                    "gpg",
                    "--batch",
                    "--yes",
                    "--quiet",
                    "--output",
                    path.with_suffix(""),
                    "--decrypt",
                    path,
                ]
            )


if __name__ == "__main__":
    main()
