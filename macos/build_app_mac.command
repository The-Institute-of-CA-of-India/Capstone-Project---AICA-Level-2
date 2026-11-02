#!/bin/bash
# ==========================================================================
#  FS Hard Copy Review - build a self-contained macOS app
#  Output: dist/FS Hard Copy Review.app  and  dist/FS_Hard_Copy_Review_mac.zip
#  Build on a Mac with the same chip type as the users (Apple silicon / Intel).
# ==========================================================================
cd "$(dirname "$0")" || exit 1
VPY="$PWD/.venv-mac/bin/python"

echo " [1/4] Preparing the Python environment …"
bash ./run_tool_mac.command --setup-only || { echo " Environment setup failed."; read -r; exit 1; }

echo " [2/4] Installing PyInstaller …"
"$VPY" -m pip install --upgrade pyinstaller -q --disable-pip-version-check || { read -r; exit 1; }

echo " [3/4] Creating the application icon …"
mkdir -p build
"$VPY" fs_hard_copy_review.py --make-icon build/app.icns

echo " [4/4] Building the app (takes a few minutes) …"
OCR_ARGS=()
"$VPY" -c "import rapidocr_onnxruntime" 2>/dev/null && OCR_ARGS=(--collect-all rapidocr_onnxruntime --collect-all onnxruntime)
"$VPY" -m PyInstaller --noconfirm --clean --windowed \
    --name "FS Hard Copy Review" \
    --icon "$PWD/build/app.icns" \
    --osx-bundle-identifier com.robo.fshardcopyreview \
    --collect-data docx --collect-data pdfminer \
    --collect-all pypdfium2 --collect-all pypdfium2_raw \
    "${OCR_ARGS[@]}" \
    --collect-data wordninja \
    --hidden-import keyring.backends.macOS \
    --exclude-module tkinter \
    --distpath dist --workpath build/work --specpath build \
    "$PWD/fs_hard_copy_review.py" || { echo " Build failed - see above."; read -r; exit 1; }

cd dist && ditto -c -k --sequesterRsrc --keepParent "FS Hard Copy Review.app" FS_Hard_Copy_Review_mac.zip
echo
echo " Done: dist/FS Hard Copy Review.app  (share dist/FS_Hard_Copy_Review_mac.zip)"
open .
read -r -p " Press Enter to close…"
