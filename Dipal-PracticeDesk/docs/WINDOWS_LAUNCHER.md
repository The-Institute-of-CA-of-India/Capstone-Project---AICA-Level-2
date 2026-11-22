# Isolated Windows launcher

Double-click START_WINDOWS.cmd from the extracted project folder. Chrome is preferred; Edge is used if Chrome is absent from the checked standard paths. Each normal launch requests a unique temporary user-data directory plus incognito/InPrivate mode. Only installed trusted browser executables in standard locations are selected.

No administrator rights, browser download, registry edits, security-policy changes, default-profile edits or forced logout are performed. The script never reads passwords/tokens or enables remote debugging. If no supported browser or usable temporary folder is found, it stops instead of falling back into the normal multi-account browser.

Managed browser policy can override these settings. This is an account-conflict mitigation, not a guarantee that Google deployment, consent, quota or access errors cannot occur. Faculty must use one Google account in the new session and review Google authorization themselves.

The profile directory is left under Windows TEMP. No recursive deletion is included. Close the private window when finished. Keep any downloaded exports/backups appropriately private.

For a non-launching installation check, run START_WINDOWS.cmd /check. This checks the executable path and planned mode only; it does not verify the app, sign-in or real isolation in a running browser.
