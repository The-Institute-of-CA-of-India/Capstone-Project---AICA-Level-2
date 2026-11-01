"""The CA firm this copy of the application is made for.

build_exe.py writes the firm's name and address into a temporary copy of
this file when building that firm's .exe (this source file is never
changed), so the details are compiled into the program and cannot be
changed by its users. Running from the source code, the values below are
used.
"""
FIRM_NAME = ""
FIRM_ADDRESS = ""  # lines separated by "\n"


def address_lines():
    return [line.strip() for line in FIRM_ADDRESS.splitlines() if line.strip()]


def window_title():
    return f"{FIRM_NAME} - DSC Management Tool" if FIRM_NAME else "DSC Management Tool"


def report_header(report_title):
    """Rows printed above the table in every exported report."""
    rows = [[FIRM_NAME]] if FIRM_NAME else []
    rows += [[line] for line in address_lines()]
    rows.append([report_title])
    return rows
