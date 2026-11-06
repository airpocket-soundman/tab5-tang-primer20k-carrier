"""Compare per-net total track length: KiCad (unique segments) vs EasyEDA (import-compat/etracks.json, ktracks.json)."""
import json, collections
from pathlib import Path
D = Path(__file__).resolve().parent / 'import-compat'
e = json.load(open(D / 'etracks.json'))['result']['per']
k = json.load(open(D / 'ktracks.json'))['per']
en, kn = collections.defaultdict(float), collections.defaultdict(float)
ec, kc = collections.Counter(), collections.Counter()
for key, v in e.items():
    net = key.split('|')[0]; en[net] += v['len']; ec[net] += v['n']
for key, v in k.items():
    net = key.split('|')[0]; kn[net] += v['len']; kc[net] += v['n']
bad = []
for net in sorted(set(en) | set(kn)):
    if abs(en[net] - kn[net]) > 0.05:
        bad.append((net, round(kn[net], 3), round(en[net], 3), kc[net], ec[net]))
print('nets compared', len(set(en) | set(kn)), 'nets with length difference > 0.05 mm:', len(bad))
print('total length KiCad', round(sum(kn.values()), 1), 'EasyEDA', round(sum(en.values()), 1))
for b in bad[:15]: print(' ', b, '(net, kicad_mm, easyeda_mm, kicad_n, easyeda_n)')
