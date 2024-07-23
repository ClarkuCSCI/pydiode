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
        # We have a secret key for all but the last file
        encrypted_files = [
            Path("1.txt.gpg"),
            Path("2.txt.gpg"),
            Path("3.txt.gpg"),
            Path("msg.gpg"),
        ]
        decrypted_files = {
            Path("1.txt"): "ABC",
            Path("2.txt"): "DEF",
            Path("3.txt"): "GHI",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy the encrypted files
            for file in encrypted_files:
                shutil.copy(PARENT_DIR / file, tmpdir)

            # Decrypt the files
            decrypt = subprocess.run(
                [sys.executable, "-m", "pydiode.decrypt"],
                input="\n".join([str(tmpdir / f) for f in encrypted_files]),
                capture_output=True,
                check=True,
                text=True,
            )

            # Check the files were decrypted
            for file, data in decrypted_files.items():
                with open(tmpdir / file, "r") as f:
                    self.assertEqual(data, f.read().strip())

            # The properly decrypted files should be deleted
            for file in encrypted_files[:-1]:
                self.assertFalse((tmpdir / file).exists())
            # The file that wan't decrypted should exist
            self.assertTrue((tmpdir / encrypted_files[-1]).exists())
