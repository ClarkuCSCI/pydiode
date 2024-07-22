from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PARENT_DIR = Path(__file__).parent


class TestDecrypt(unittest.TestCase):
    def setUp(self):
        subprocess.run(
            ["gpg", "--import", PARENT_DIR / "PRIVATE.asc"],
            capture_output=True,
            check=True,
        )

    def test_decrypt(self):
        files = {
            Path("1.txt.gpg"): "ABC",
            Path("2.txt.gpg"): "DEF",
            Path("3.txt.gpg"): "GHI",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy the encrypted files
            for file in files:
                shutil.copy(PARENT_DIR / file, tmpdir)

            # Decrypt the files
            decrypt = subprocess.run(
                [sys.executable, "-m", "pydiode.decrypt"],
                input="\n".join([str(tmpdir / file) for file in files.keys()]),
                text=True,
            )

            # Check the files were decrypted
            for file, data in files.items():
                with open(tmpdir / file.with_suffix(""), "r") as f:
                    self.assertEqual(data, f.read().strip())
