"""Offline native desktop interface for the compatible PQCWEB01 envelope."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm
from crypto_core import MAX_FILE, HEADER_SIZE, decrypt, encrypt, fingerprint, generate_keys

BG = '#0c1422'
PANEL = '#132237'
TEXT = '#e7edf5'
MUTED = '#a9b8cb'
ACCENT = '#71e5c5'


def read_limited(path, limit):
    with Path(path).open('rb') as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError('The selected file exceeds the allowed size.')
    return data


def save_new(path, data):
    """Never replace existing files, including through symlinks."""
    with Path(path).open('xb') as destination:
        destination.write(data)


class VaultApp:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.results = queue.Queue()
        self.buttons = []
        root.title('PQC Vault — Desktop')
        root.geometry('900x760')
        root.minsize(760, 730)
        root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.configure_style()

        shell = ttk.Frame(root, padding=20)
        shell.pack(fill='both', expand=True)
        top = ttk.Frame(shell)
        top.pack(fill='x')
        ttk.Label(top, text='◈  PQC VAULT', style='Brand.TLabel').pack(side='left')
        ttk.Label(top, text='OFFLINE DESKTOP', style='Accent.TLabel').pack(side='right')
        ttk.Label(shell, text='Your files. Your keys.', style='Hero.TLabel').pack(anchor='w', pady=(16, 6))
        ttk.Label(shell, text='Post-quantum file protection on your computer.', style='Muted.TLabel').pack(anchor='w')
        ttk.Label(shell, text='ML-KEM-768  /  HKDF-SHA256  /  AES-256-GCM', style='Accent.TLabel').pack(anchor='w', pady=(14, 18))

        footer = ttk.Frame(shell)
        footer.pack(side='bottom', fill='x')
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill='both', expand=True)
        self.keys = self.tab('01  Create keys')
        self.enc = self.tab('02  Encrypt file')
        self.dec = self.tab('03  Decrypt file')

        self.heading(self.keys, 'Create your key pair',
            'Share the public key. Keep the protected private key and password confidential.')
        self.key_password = self.password(self.keys, 'Private-key password · at least 12 characters')
        self.key_confirm = self.password(self.keys, 'Confirm password')
        self.action(self.keys, 'Generate and save key pair', self.create_keys)
        self.note(self.keys, 'Save both keys in a secure location. A lost private key or password cannot be recovered.')

        self.heading(self.enc, 'Encrypt for a recipient',
            'Choose a recipient public key and a file up to 10 MiB. The original file is preserved.')
        self.public_path = self.file_picker(self.enc, 'Recipient public key', [('PEM public key', '*.pem')])
        self.plain_path = self.file_picker(self.enc, 'File to encrypt', [('All files', '*.*')])
        self.action(self.enc, 'Encrypt and save file', self.encrypt_file)
        self.note(self.enc, 'Verify the recipient fingerprint through a trusted channel before approving encryption.')

        self.heading(self.dec, 'Recover your file',
            'Use the private key matching the public key used for encryption.')
        self.private_path = self.file_picker(self.dec, 'Protected private key', [('PEM private key', '*.pem')])
        self.encrypted_path = self.file_picker(self.dec, 'Encrypted file', [('PQC encrypted file', '*.pqc'), ('All files', '*.*')])
        self.decrypt_password = self.password(self.dec, 'Private-key password')
        self.action(self.dec, 'Decrypt and save file', self.decrypt_file)

        self.progress = ttk.Progressbar(footer, mode='indeterminate')
        self.progress.pack(fill='x', pady=(18, 8))
        self.status = tk.StringVar(value='Ready. All cryptographic processing stays on this computer.')
        self.status_label = ttk.Label(footer, textvariable=self.status, style='Muted.TLabel', wraplength=700)
        self.status_label.pack(fill='x')
        self.fingerprint = tk.StringVar()
        ttk.Label(footer, text='Public-key SHA-256 fingerprint', style='Muted.TLabel').pack(anchor='w', pady=(14, 4))
        ttk.Entry(footer, textvariable=self.fingerprint, state='readonly').pack(fill='x')
        ttk.Label(footer, text='Local prototype · No sender authentication · Not a FIPS-validated product',
                  style='Footer.TLabel').pack(anchor='w', pady=(14, 0))
        self.tabs.bind('<<NotebookTabChanged>>', self.clear_passwords)
        self.poll_id = root.after(80, self.poll)

    def configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=TEXT, font=('Segoe UI', 10))
        style.configure('TFrame', background=BG)
        style.configure('Panel.TFrame', background=PANEL)
        style.configure('TLabel', background=BG, foreground=TEXT)
        style.configure('Panel.TLabel', background=PANEL)
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('Accent.TLabel', foreground=ACCENT, font=('Segoe UI', 10, 'bold'))
        style.configure('Brand.TLabel', font=('Segoe UI', 17, 'bold'))
        style.configure('Hero.TLabel', font=('Segoe UI', 24, 'bold'))
        style.configure('Heading.TLabel', background=PANEL, font=('Segoe UI', 19, 'bold'))
        style.configure('Footer.TLabel', foreground=MUTED, font=('Segoe UI', 9))
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', background='#1a2d44', foreground=MUTED, padding=(20, 13))
        style.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', ACCENT)])
        style.configure('TEntry', fieldbackground='#0d1828', foreground=TEXT, insertcolor=TEXT, padding=9)
        style.configure('TButton', background='#29425b', foreground=TEXT, padding=(15, 10))
        style.map('TButton', background=[('active', '#375874')])
        style.configure('Primary.TButton', background=ACCENT, foreground='#0c252a', font=('Segoe UI', 10, 'bold'))
        style.map('Primary.TButton', background=[('active', '#9ef5dc'), ('disabled', '#365b58')])
        style.configure('TProgressbar', background=ACCENT, troughcolor=PANEL)

    def tab(self, label):
        outer = ttk.Frame(self.tabs, style='Panel.TFrame')
        self.tabs.add(outer, text=label)
        canvas = tk.Canvas(outer, background=PANEL, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        frame = ttk.Frame(canvas, padding=20, style='Panel.TFrame')
        item = canvas.create_window((0, 0), window=frame, anchor='nw')
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(item, width=event.width))
        frame.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta / 120), 'units'))
        return frame

    def heading(self, parent, title, description):
        ttk.Label(parent, text=title, style='Heading.TLabel').pack(anchor='w', pady=(0, 10))
        ttk.Label(parent, text=description, style='Panel.TLabel', wraplength=780).pack(anchor='w', pady=(0, 8))

    def password(self, parent, label):
        ttk.Label(parent, text=label, style='Panel.TLabel').pack(anchor='w', pady=(12, 6))
        entry = ttk.Entry(parent, show='●')
        entry.pack(fill='x')
        return entry

    def file_picker(self, parent, label, types):
        ttk.Label(parent, text=label, style='Panel.TLabel').pack(anchor='w', pady=(12, 6))
        row = ttk.Frame(parent, style='Panel.TFrame')
        row.pack(fill='x')
        value = tk.StringVar()
        ttk.Entry(row, textvariable=value, state='readonly').pack(side='left', fill='x', expand=True)
        def browse():
            selected = filedialog.askopenfilename(parent=self.root, title=label, filetypes=types)
            if selected:
                value.set(selected)
        button = ttk.Button(row, text='Browse…', command=browse)
        button.pack(side='right', padx=(8, 0))
        self.buttons.append(button)
        return value

    def action(self, parent, title, command):
        button = ttk.Button(parent, text=title, style='Primary.TButton', command=command)
        button.pack(anchor='w', pady=(22, 8))
        self.buttons.append(button)

    def note(self, parent, text):
        ttk.Label(parent, text=text, style='Panel.TLabel', wraplength=780).pack(anchor='w', pady=(12, 0))

    def clear_passwords(self, event=None):
        for entry in (self.key_password, self.key_confirm, self.decrypt_password):
            entry.delete(0, 'end')

    def error(self, error):
        if isinstance(error, InvalidTag):
            text = 'Decryption failed. The private key does not match, or the file has been altered.'
        elif isinstance(error, UnsupportedAlgorithm):
            text = 'This cryptography installation does not support ML-KEM-768.'
        elif isinstance(error, FileExistsError):
            text = 'That output file already exists. Choose a new filename. Nothing was overwritten.'
        elif isinstance(error, (ValueError, TypeError)):
            text = str(error) or 'Check the selected file, key and password.'
        elif isinstance(error, OSError):
            text = f'File operation failed: {error}'
        else:
            text = 'Processing failed. Check your files and cryptography installation.'
        self.status.set(text)
        messagebox.showerror('PQC Vault', text, parent=self.root)

    def start(self, work, complete):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.state(['disabled'])
        self.progress.start(12)
        self.status.set('Processing locally…')
        def run():
            try:
                self.results.put((complete, work(), None))
            except Exception as error:
                self.results.put((complete, None, error))
        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            complete, result, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            for button in self.buttons:
                button.state(['!disabled'])
            try:
                if error:
                    self.error(error)
                else:
                    complete(result)
            except Exception as failure:
                self.error(failure)
        self.poll_id = self.root.after(80, self.poll)

    def create_keys(self):
        password = self.key_password.get()
        if len(password) < 12:
            return self.error(ValueError('Use a password of at least 12 characters.'))
        if password != self.key_confirm.get():
            return self.error(ValueError('Passwords do not match.'))
        folder = filedialog.askdirectory(parent=self.root, title='Choose a folder for both keys')
        if not folder:
            return
        self.clear_passwords()
        def complete(pair):
            public, private = pair
            digest = fingerprint(public)
            stem = 'pqc-' + digest[:16]
            private_file = Path(folder) / (stem + '-private.pem')
            public_file = Path(folder) / (stem + '-public.pem')
            save_new(private_file, private)
            try:
                save_new(public_file, public)
            except Exception as error:
                raise OSError(f'Private key saved to {private_file}, but public key could not be saved: {error}') from error
            self.fingerprint.set(digest)
            self.public_path.set(str(public_file))
            self.private_path.set(str(private_file))
            self.status.set(f'Both keys saved in {folder}. Back up the protected private key and password securely.')
            messagebox.showinfo('Keys saved', f'Public key: {public_file.name}\nPrivate key: {private_file.name}\n\nShare only the public key.', parent=self.root)
        self.start(lambda: generate_keys(password), complete)

    def encrypt_file(self):
        try:
            if not self.public_path.get() or not self.plain_path.get():
                raise ValueError('Select both a recipient public key and a file.')
            public = read_limited(self.public_path.get(), 16384)
            digest = fingerprint(public)
            self.fingerprint.set(digest)
            if not messagebox.askyesno('Verify recipient', 'Confirm this fingerprint matches the recipient’s public key through a trusted channel:\n\n' + digest + '\n\nProceed with encryption?', parent=self.root):
                return
            source = self.plain_path.get()
            output = filedialog.asksaveasfilename(parent=self.root, title='Save encrypted file (choose a new filename)', initialfile=Path(source).name + '.pqc', defaultextension='.pqc', filetypes=[('PQC encrypted file', '*.pqc')])
            if not output:
                return
            def complete(data):
                save_new(output, data)
                self.status.set(f'Encrypted file saved: {output}. The original file was preserved.')
            self.start(lambda: encrypt(read_limited(source, MAX_FILE), public), complete)
        except Exception as error:
            self.error(error)

    def decrypt_file(self):
        try:
            if not self.private_path.get() or not self.encrypted_path.get() or not self.decrypt_password.get():
                raise ValueError('Select a private key, an encrypted file, and enter the private-key password.')
            private_path = self.private_path.get()
            source = self.encrypted_path.get()
            password = self.decrypt_password.get()
            name = Path(source).name
            if name.lower().endswith('.pqc'):
                name = name[:-4]
            output = filedialog.asksaveasfilename(parent=self.root, title='Save restored file (choose a new filename)', initialfile='restored-' + (name or 'file'), filetypes=[('All files', '*.*')])
            if not output:
                return
            self.clear_passwords()
            def complete(data):
                save_new(output, data)
                self.status.set(f'Decrypted file saved and integrity verified: {output}')
            self.start(lambda: decrypt(read_limited(source, MAX_FILE + HEADER_SIZE + 16), read_limited(private_path, 16384), password), complete)
        except Exception as error:
            self.error(error)

    def close(self):
        if self.busy:
            messagebox.showinfo('Processing', 'Please wait for the current operation to finish before closing.', parent=self.root)
            return
        self.clear_passwords()
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    root = tk.Tk()
    VaultApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
