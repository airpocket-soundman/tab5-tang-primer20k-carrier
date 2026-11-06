"""Compare the EasyEDA pad/net export (import-compat/pads.json, from export-pad-nets.js) with the KiCad pads
(import-compat/kpads.json, from kicad_pads.py). Matching is by pad number + position (EasyEDA y is inverted)."""
import json, collections, sys
from pathlib import Path
D = Path(__file__).resolve().parent / 'import-compat'
e = json.load(open(D / 'pads.json'))['result']
k = json.load(open(D / 'kpads.json'))
def key(num, x, y): return (str(num), round(x * 100), round(y * 100))
ek = collections.defaultdict(list)
for ref, num, net, x, y in e['pads']:
    ek[key(num, x, -y)].append(net)
kk = collections.defaultdict(list)
for ref, num, net, x, y in k['pads']:
    kk[key(num, x, y)].append((net, ref))
miss, netdiff, samples = 0, 0, []
for kx, lst in kk.items():
    cand = ek.get(kx)
    if not cand:
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                c = ek.get((kx[0], kx[1] + dx, kx[2] + dy))
                if c: cand = c; break
            if cand: break
    if not cand:
        miss += len(lst); samples.append(('no EasyEDA pad', kx, lst)); continue
    for net, ref in lst:
        if net not in cand and not (net.startswith('unconnected') and '' in cand):
            netdiff += 1; samples.append(('net differs', ref, kx[0], 'kicad:', net, 'easyeda:', cand))
res = {'kicad_pads': sum(len(v) for v in kk.values()), 'easyeda_pads': len(e['pads']), 'missing_in_easyeda': miss, 'net_differences': netdiff,
       'nets_only_in_kicad': sorted(set(k['nets']) - set(e['nets'])), 'nets_only_in_easyeda': sorted(set(e['nets']) - set(k['nets']))}
print(json.dumps(res, ensure_ascii=False))
for s in samples[:15]: print(s)
