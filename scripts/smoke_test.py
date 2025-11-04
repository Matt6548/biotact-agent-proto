from pathlib import Path
out = Path("samples/outputs/pipeline_markdown.md")
if not out.exists() or out.stat().st_size == 0:
    raise SystemExit("FAIL: output file not found or empty")
txt = out.read_text(encoding="utf-8", errors="ignore")
need = ["Content Plan","Brief","Brand","Knowledge"]
miss = [w for w in need if w.lower() not in txt.lower()]
if miss:
    raise SystemExit("FAIL: sections not found -> " + ", ".join(miss))
print("PASS:", out, "size =", out.stat().st_size, "bytes")