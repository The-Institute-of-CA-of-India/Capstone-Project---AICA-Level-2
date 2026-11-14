import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import itr_schema_parser
assert callable(itr_schema_parser.extract)
print("ITR schema parser import OK; financial accuracy requires real-world validation")
