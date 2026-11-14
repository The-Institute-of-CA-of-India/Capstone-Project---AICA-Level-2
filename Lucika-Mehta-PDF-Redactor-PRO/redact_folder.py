"""
Redact every supported file in a folder from the command line.

    python redact_folder.py "D:\\Clients\\Sample Traders\\AY 2024-25"
    python redact_folder.py FOLDER --labels --subfolders --password AAKC1504 --pan AAKCS1234F --dob 15/04/1980

Outputs go to "<folder> - Redacted"; the certificate, log and label key go to
"<folder> - Redaction records (do not upload)".
"""

import argparse
import sys

from redact import batch as B
from redact import detect as D
from redact import outputs as O
from redact.model import Options


def main():
    ap = argparse.ArgumentParser(description="Bulk redaction of a client folder")
    ap.add_argument("folder")
    ap.add_argument("--subfolders", action="store_true", help="include sub-folders")
    ap.add_argument("--labels", action="store_true", help="labelled boxes [ACCT-1] instead of black boxes")
    ap.add_argument("--profile", default="auto", choices=["auto", "bank", "notice", "kyc", "asis"])
    ap.add_argument("--password", action="append", default=[], help="password to try (repeatable)")
    ap.add_argument("--pan", action="append", default=[], help="client PAN for password formats")
    ap.add_argument("--dob", action="append", default=[], help="date of birth/incorporation DD/MM/YYYY")
    ap.add_argument("--name", action="append", default=[], help="client name for password formats")
    ap.add_argument("--word", action="append", default=[], help="client-specific word to redact")
    ap.add_argument("--contacts", action="store_true", help="also redact mobile numbers and e-mails")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--lang", default="eng", help="OCR languages, e.g. eng+hin+mar")
    ap.add_argument("--anonymise", action="store_true", help="name outputs Document_01, 02 ...")
    ap.add_argument("--combined", action="store_true", help="also create one combined PDF")
    ap.add_argument("--workers", type=int, default=B.default_workers())
    ap.add_argument("--reviewer", default="")
    a = ap.parse_args()

    rules = set(D.DEFAULT_RULES)
    if a.contacts:
        rules |= {"MOBILE", "EMAIL"}
    opts = Options(rules=rules, profile=a.profile, style="label" if a.labels else "black",
                   custom_terms=a.word, passwords=a.password,
                   password_hints={"pans": a.pan, "dates": a.dob, "names": a.name},
                   ocr_mode="off" if a.no_ocr else "auto", ocr_langs=tuple(a.lang.split("+")),
                   anonymise_names=a.anonymise, workers=a.workers)
    files = O.collect_folder(a.folder, a.subfolders, B.SUPPORTED_EXT)
    if not files:
        print("No supported files found.")
        return 1
    print(f"{len(files)} file(s) found. Working…")

    def progress(stage, done, total, name):
        print(f"  {stage} {done}/{total}: {name}")

    b = B.run_batch(files, opts, progress)
    out_dir, rec_dir = O.write_folder_outputs(b, a.folder, text=True, tables=True, combined=a.combined,
                                              preparer=a.reviewer)
    print()
    for row in O.log_rows(b):
        print(f"{row['File'][:45]:45}  {row['Items redacted']:>4} items  {row['Re-check']:<12} {row['Status']}")
    print(f"\nRedacted files : {out_dir}\nRecords (keep) : {rec_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
