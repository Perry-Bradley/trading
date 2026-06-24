import os
from pathlib import Path

# 1. Update app.py
app_path = Path("src/webapp/app.py")
text = app_path.read_text(encoding="utf-8")

# Fix api_analysis to accept tf
text = text.replace(
    'pair = request.args.get("pair", config.PAIRS[0])\n    if not _seeded():',
    'pair = request.args.get("pair", config.PAIRS[0])\n    tf = request.args.get("tf", TF)\n    if not _seeded():'
)
text = text.replace(
    'c = _ANALYSIS_CACHE.get(pair)',
    'c = _ANALYSIS_CACHE.get(f"{pair}_{tf}")'
)
text = text.replace(
    'df = load(pair, TF)',
    'df = load(pair, tf)'
)
text = text.replace(
    '"tf": TF,',
    '"tf": tf,'
)
text = text.replace(
    '_ANALYSIS_CACHE[pair] = (time.time(), out)',
    '_ANALYSIS_CACHE[f"{pair}_{tf}"] = (time.time(), out)'
)
app_path.write_text(text, encoding="utf-8")
print("app.py patched")

# 2. Update api.ts
api_path = Path("web/lib/api.ts")
text = api_path.read_text(encoding="utf-8")
text = text.replace(
    'analysis: (pair: string) => j<Analysis>(`/api/analysis?pair=${pair}`),',
    'analysis: (pair: string, tf?: string) => j<Analysis>(`/api/analysis?pair=${pair}${tf ? `&tf=${tf}` : ""}`),'
)
api_path.write_text(text, encoding="utf-8")
print("api.ts patched")

# 3. Update pairs/page.tsx
pairs_path = Path("web/app/pairs/page.tsx")
text = pairs_path.read_text(encoding="utf-8")

text = text.replace('const [sel, setSel] = useState<string>("");', 'const [sel, setSel] = useState<string>("");\n  const [selTf, setSelTf] = useState<string>("");')

text = text.replace(
"""      const p = new URLSearchParams(window.location.search).get("p");
      setSel(p && c.pairs.includes(p) ? p : c.pairs[0]);""",
"""      const sp = new URLSearchParams(window.location.search);
      const p = sp.get("p");
      const tf = sp.get("tf");
      setSel(p && c.pairs.includes(p) ? p : c.pairs[0]);
      setSelTf(tf && ["H4", "H1", "M30"].includes(tf) ? tf : c.tf);"""
)

text = text.replace(
"""  const load = useCallback(async () => {
    if (!sel) return;
    try { setA(await api.analysis(sel)); setBust(Date.now()); } catch { /* */ }
  }, [sel]);""",
"""  const load = useCallback(async () => {
    if (!sel || !selTf) return;
    try { setA(await api.analysis(sel, selTf)); setBust(Date.now()); } catch { /* */ }
  }, [sel, selTf]);"""
)

text = text.replace(
"""          <div className="flex flex-wrap items-center gap-3">
            <span className="text-2xl font-bold">{a.pair}</span>
            <DirBadge dir={a.bias} />""",
"""          <div className="flex flex-wrap items-center gap-3">
            <span className="text-2xl font-bold">{a.pair}</span>
            <div className="flex gap-1 ml-2 bg-line/20 p-1 rounded-lg">
              {["H4", "H1", "M30"].map(t => (
                <button key={t} onClick={() => { setSelTf(t); setA(null); }} className={`px-2 py-0.5 text-xs font-bold rounded ${selTf === t ? "bg-brand text-white" : "text-sub hover:text-ink"}`}>{t}</button>
              ))}
            </div>
            <DirBadge dir={a.bias} />"""
)

pairs_path.write_text(text, encoding="utf-8")
print("pairs/page.tsx patched")

# 4. Update signals/page.tsx
signals_path = Path("web/app/signals/page.tsx")
text = signals_path.read_text(encoding="utf-8")
text = text.replace(
    'href={`/pairs?p=${s.pair}`}',
    'href={`/pairs?p=${s.pair}&tf=${s.tf || "H4"}`}'
)
signals_path.write_text(text, encoding="utf-8")
print("signals/page.tsx patched")

