# Building Investor Manager

The released app has three parts, all next to each other:

```
Investor Manager_vX.Y.exe        the launcher (launcher/launcher.c)
App Files/
    setup.cmd                    first-run setup (installer/setup.cmd)
    Start_vX.Y.bat               same as the exe, in case the exe is ever blocked
    app_vX.Y.zip                 the Python program: app/ packed as app/vX.Y/...
    runtime_*.zip                portable Python 3.12 with all libraries (python/ ...)
    tesseract.zip                Tesseract OCR (tesseract/ ...)
```

On first run the launcher calls `setup.cmd`, which unpacks the runtime, Tesseract and the version's app
into `%LOCALAPPDATA%\ContractNoteManager`. Each version is kept in its own `app\vX.Y` folder, so older
exes keep working. Data stays in `Data` next to the exe.

## 1. Portable Python runtime

1. Download a Windows x86_64 CPython 3.12 "install_only" build from
   [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases) and unpack
   it to `python/`.
2. Install the libraries into it as Windows wheels (from any OS, with [uv](https://github.com/astral-sh/uv)):

   ```
   uv pip install --python-platform x86_64-pc-windows-msvc --python-version 3.12 --only-binary :all: \
       --target python/Lib/site-packages -r requirements.txt
   ```
3. Zip the `python` folder as `runtime_1.zip` (split into several zips if you need smaller files).

## 2. Tesseract OCR

Install Tesseract 5 for Windows, copy its folder as `tesseract/` (with `tessdata/eng.traineddata`) and zip
it as `tesseract.zip`.

## 3. The app zip

Pack the `app` folder of this repository as `app/vX.Y/` inside `app_vX.Y.zip` (no `__pycache__`).

## 4. The launcher exe

With MinGW-w64 (for example `x86_64-w64-mingw32-gcc` on Linux, or MSYS2 on Windows), after setting the
version numbers in `launcher/version.rc`:

```
x86_64-w64-mingw32-windres launcher/version.rc -O coff -o version.res
x86_64-w64-mingw32-gcc -Os -s -municode -mwindows -DAPPVER='L"vX.Y"' launcher/launcher.c version.res \
    -o "Investor Manager_vX.Y.exe" -lshell32 -luser32 -lshlwapi
```

## 5. Start .bat

Copy `installer/Start_vX.bat` to `App Files/Start_vX.Y.bat` and replace the version in it.

## Environment variables the app reads

| Variable | Meaning |
|---|---|
| `CNM_VERSION` | Version shown in the app, e.g. `v1.13` |
| `CNM_DATA` | Data folder (default: `Data` in the current folder) |
| `CNM_TESSERACT` | Path of `tesseract.exe` |
| `CNM_PORT` | Port of the local server (default 8765) |
| `CNM_NO_WINDOW` | Set to 1 to start the server without opening the app window |
| `CNM_AUTOCLOSE` | Set to 0 to keep the server running after the window is closed |
