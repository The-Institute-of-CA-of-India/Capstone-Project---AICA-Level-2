"""Output document builders; they accept approved CaseFiles only (SPEC §11).

``build_all`` writes the report, draft grounds, paper book index and issue register for a matter
and tries to convert the report to PDF. The implementation lives in the compiled
:mod:`appealiq.outputs._builder` module (CR-011); the names are re-exported here.
"""

from __future__ import annotations

from appealiq.outputs._builder import OutputBundle, build_all, output_names
from appealiq.outputs.styles import OutputContext, OutputError

__all__ = ["OutputBundle", "OutputContext", "OutputError", "build_all", "output_names"]
