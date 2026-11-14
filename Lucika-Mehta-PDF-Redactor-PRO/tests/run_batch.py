import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from redact import batch as B, outputs as O, detect as D
from redact.model import Options
S = Path(sys.argv[1]); style = sys.argv[2] if len(sys.argv) > 2 else "label"; workers = int(sys.argv[3]) if len(sys.argv) > 3 else 1

def main():
    opts = Options(rules=set(D.DEFAULT_RULES), style=style, workers=workers,
                   password_hints={"pans": ["AAKCS1234F"], "dates": ["15/04/1980"], "names": ["Sample Traders"]})
    files = [(p.name, p.read_bytes()) for p in sorted(S.glob("[0-9]*"))]
    t = time.time()
    b = B.run_batch(files, opts, progress=lambda st, d, n, name: None)
    print(f"done in {time.time()-t:.1f}s")
    for row in O.log_rows(b):
        print(f"{row['File'][:30]:30} {row['Detected type']:18} items={row['Items redacted']:3} {row['Re-check']:10} {row['Status'][:70]}")
    out = S / ("out_" + style); out.mkdir(exist_ok=True)
    names = O.output_names(b)
    for r in b.results:
        if r.output: (out / Path(names[r.name]).name).write_bytes(r.output)
    (out / "ai.zip").write_bytes(O.ai_zip(b, combined=True)); (out / "records.zip").write_bytes(O.records_zip(b, "CA Test"))
    import pickle; pickle.dump(b, open(out / "batch.pkl", "wb"))


if __name__ == '__main__':
    main()
