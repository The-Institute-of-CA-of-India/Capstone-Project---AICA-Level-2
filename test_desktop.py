"""Exercise the real desktop callbacks with controlled native dialogs."""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_app import VaultApp, read_limited, save_new


class FileTests(unittest.TestCase):
    def test_save_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'existing.bin'
            save_new(path, b'original')
            with self.assertRaises(FileExistsError):
                save_new(path, b'replacement')
            self.assertEqual(path.read_bytes(), b'original')

    def test_bounded_read(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'sample.bin'
            path.write_bytes(b'12345')
            with self.assertRaises(ValueError):
                read_limited(path, 4)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = VaultApp(self.root)
        self.root.update()
        self.errors = []
        self.patches = [
            patch('desktop_app.messagebox.showerror', side_effect=lambda title, text, **kw: self.errors.append(text)),
            patch('desktop_app.messagebox.showinfo'),
            patch('desktop_app.messagebox.askyesno', return_value=True),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.app.close()

    def finish(self):
        deadline = time.monotonic() + 15
        while self.app.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.app.busy, 'Desktop worker did not finish')

    def test_password_mismatch(self):
        self.app.key_password.insert(0, 'desktop-test-password')
        self.app.key_confirm.insert(0, 'different-password')
        self.app.create_keys()
        self.assertIn('Passwords do not match.', self.errors)

    def test_full_desktop_flow_and_tamper(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            directory = Path(folder)
            plain = directory / 'sample.bin'
            encrypted = directory / 'sample.bin.pqc'
            restored = directory / 'restored.bin'
            rejected = directory / 'must-not-exist.bin'
            content = bytes(range(256)) * 16
            plain.write_bytes(content)
            password = 'desktop-test-password'
            self.app.key_password.insert(0, password)
            self.app.key_confirm.insert(0, password)
            with patch('desktop_app.filedialog.askdirectory', return_value=folder):
                self.app.create_keys()
                self.finish()
            self.assertEqual(len(list(directory.glob('*.pem'))), 2)
            self.assertEqual(self.app.key_password.get(), '')
            self.app.plain_path.set(str(plain))
            with patch('desktop_app.filedialog.asksaveasfilename', return_value=str(encrypted)):
                self.app.encrypt_file()
                self.finish()
            self.app.encrypted_path.set(str(encrypted))
            self.app.decrypt_password.insert(0, password)
            with patch('desktop_app.filedialog.asksaveasfilename', return_value=str(restored)):
                self.app.decrypt_file()
                self.finish()
            self.assertEqual(restored.read_bytes(), content)
            self.assertEqual(plain.read_bytes(), content)
            self.assertEqual(self.app.decrypt_password.get(), '')
            self.assertEqual(self.errors, [])
            corrupted = bytearray(encrypted.read_bytes())
            corrupted[-1] ^= 1
            encrypted.write_bytes(corrupted)
            self.app.decrypt_password.insert(0, password)
            with patch('desktop_app.filedialog.asksaveasfilename', return_value=str(rejected)):
                self.app.decrypt_file()
                self.finish()
            self.assertFalse(rejected.exists())
            self.assertIn('Decryption failed', self.errors[-1])


if __name__ == '__main__':
    unittest.main()
