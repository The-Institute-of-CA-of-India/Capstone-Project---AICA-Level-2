"""Write cashsense/db/supabase_setup.sql (schema + Row Level Security) for the Supabase SQL editor."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cashsense.db.adapter import supabase_setup_sql  # noqa: E402

out = ROOT / "cashsense" / "db" / "supabase_setup.sql"
out.write_text(supabase_setup_sql(), encoding="utf-8")
print("Wrote", out)
