"""r5s: leave SW4 pad 6 unconnected (KiCad python). CH224A change: CFG1 must never be tied directly to VHV
(abs max 3.8 V), so the PROGRAM throw of pole B (pad 6, was PD_VDD) is left open; R73 (100k to VHV) pulls CFG1 up.

1. pad 6 loses its net; 2. the copper that only served pad 6 is found by repeatedly marking dangling PD_VDD
tracks and vias (an end that touches nothing else of the net) as dead, and only then removed. Run once.
"""
import pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
P = K / 'tab5-fpga-carrier-r5s.kicad_pcb'
b = pcbnew.LoadBoard(str(P))
mm = pcbnew.ToMM
sw = next(f for f in b.GetFootprints() if f.GetReference() == 'SW4')
pad6 = next(p for p in sw.Pads() if p.GetNumber() == '6')
assert pad6.GetNetname() == 'PD_VDD', pad6.GetNetname()
pad6.SetNetCode(0)
NET = 'PD_VDD'
def pt(x, y): return (round(mm(x), 2), round(mm(y), 2))
pads = [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == NET]
segs, vias = [], []
for t in b.GetTracks():
    if t.GetNetname() != NET:
        continue
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition()
        vias.append({'obj': t, 'at': pt(p.x, p.y), 'dead': False})
    else:
        s, e = t.GetStart(), t.GetEnd()
        segs.append({'obj': t, 'a': pt(s.x, s.y), 'b': pt(e.x, e.y), 'layer': t.GetLayer(), 'dead': False})
def on_pad(point, layer):
    v = pcbnew.VECTOR2I(int(point[0] * 1e6), int(point[1] * 1e6))
    return sum(1 for p in pads if p.IsOnLayer(layer) and p.HitTest(v, 0))
def touches(point, layer, me):
    n = on_pad(point, layer)
    n += sum(1 for s in segs if s is not me and not s['dead'] and s['layer'] == layer and point in (s['a'], s['b']))
    n += sum(1 for v in vias if not v['dead'] and v['at'] == point)
    return n
changed = True
while changed:
    changed = False
    for s in segs:
        if s['dead']:
            continue
        if touches(s['a'], s['layer'], s) == 0 or touches(s['b'], s['layer'], s) == 0:
            s['dead'] = True; changed = True
    for v in vias:
        if v['dead']:
            continue
        cnt = sum(1 for s in segs if not s['dead'] and v['at'] in (s['a'], s['b']))
        cnt += sum(1 for p in pads if p.HitTest(pcbnew.VECTOR2I(int(v['at'][0] * 1e6), int(v['at'][1] * 1e6)), 0))
        if cnt < 2:
            v['dead'] = True; changed = True
dead = [x for x in segs + vias if x['dead']]
print('SW4 pad 6 is now unconnected; copper items removed:', len(dead))
for x in dead:
    print('  ', ('via', x['at']) if 'at' in x else ('seg', b.GetLayerName(x['layer']), x['a'], x['b']))
for x in dead:
    b.Remove(x['obj'])
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(P))
