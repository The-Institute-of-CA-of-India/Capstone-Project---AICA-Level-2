FS Hard Copy Review – macOS
===========================

Copy these files into one folder on the Mac:
  fs_hard_copy_review.py, requirements.txt, run_tool_mac.command, build_app_mac.command

1) One-time (files copied from Windows lose their "run" permission):
   Open Terminal, type  cd  and a space, drag the folder into Terminal, press Enter, then run:
       chmod +x *.command

2) Run the tool:   double-click run_tool_mac.command
   First run installs Python packages (needs internet, a few minutes).
   Python 3.12 from python.org is required (3.13+ works, but without reading scanned PDFs).

3) Build a shareable app (optional):   double-click build_app_mac.command
   Result: dist/FS Hard Copy Review.app and dist/FS_Hard_Copy_Review_mac.zip

First launch on another Mac: the app is not signed by Apple, so macOS blocks it.
   Right-click the app > Open > Open   (once), or System Settings > Privacy & Security > Open Anyway.

API keys are stored in the Mac's Keychain. Reports are saved to ~/Downloads.
