"""Per-net, per-layer track count and length of the KiCad board (duplicates counted once), for comparison with
export-track-lengths.js (EasyEDA). Run with KiCad's python; writes import-compat/ktracks.json."""
import pcbnew, json, math
from pathlib import Path
H = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(str(H.parent / 'full/design/kicad/tab5-fpga-carrier-r5l.kicad_pcb'))
mm = pcbnew.ToMM
seen, per = set(), {}
for t in b.GetTracks():
    if t.GetClass() != 'PCB_TRACK': continue
    s, e = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)
    key = (t.GetLayer(), min(s, e), max(s, e), t.GetNetname())
    if key in seen: continue
    seen.add(key)
    k = t.GetNetname().lstrip('/') + '|' + b.GetLayerName(t.GetLayer())
    d = per.setdefault(k, {'n': 0, 'len': 0.0})
    d['n'] += 1
    d['len'] += math.hypot(mm(t.GetEnd().x - t.GetStart().x), mm(t.GetEnd().y - t.GetStart().y))
(H / 'import-compat').mkdir(exist_ok=True)
json.dump({'unique_segments': len(seen), 'per': per}, open(H / 'import-compat/ktracks.json', 'w'))
print(len(seen))
