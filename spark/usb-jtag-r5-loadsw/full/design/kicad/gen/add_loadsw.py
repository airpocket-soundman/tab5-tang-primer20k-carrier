"""r5l PCB step: SW4 becomes a signal-only switch and the +5V current goes through P-MOS load switches.

Source (read only): spark/usb-jtag-r5-switch/.../tab5-fpga-carrier-r5s.kicad_pcb (current r5s, never modified)
Output            : spark/usb-jtag-r5-loadsw/.../tab5-fpga-carrier-r5l.kicad_pcb
Run with KiCad's python:  "C:/Program Files/KiCad/10.0/bin/python.exe" add_loadsw.py
1. SW4 pad1 -> SW_RUN, pad3 -> SW_PGM, pad4 -> GND; the old 0.5 mm routes from those pads to the three power
   trunks are removed (the trunk ends = taps stay: BUCK_5V (38.15,26.85) F.Cu, +5V via (39.0,28.54), VBUS_PD via (39.0,31.08)).
2. 11 parts (Q11-Q15 AO3401A, D12 BZT52C6V2, R91-R95) are placed by a small search in the free corridor left of SW4
   and routed with maze.py. Result must pass KiCad DRC (done by the caller).
"""
import pcbnew, sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from maze import Router
K = Path(__file__).resolve().parents[1]
SRC = K.parents[3] / 'usb-jtag-r5-switch/full/design/kicad/tab5-fpga-carrier-r5s.kicad_pcb'
P = K / 'tab5-fpga-carrier-r5l.kicad_pcb'
SYS = Path(r'C:/Program Files/KiCad/10.0/share/kicad/footprints')
CONTRACT = json.loads((K / 'circuit-contract.json').read_text(encoding='utf8'))
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
def V(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
IO = pcbnew.PCB_IO_KICAD_SEXPR()
b = pcbnew.LoadBoard(str(SRC))
F, I2, B = pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu
# The 'POWER OFF!' reminder sat in the free corridor left of SW4: move it to the right side of SW4 (below 'SW4 MODE').
for _d in b.GetDrawings():
    if _d.GetClass() == 'PCB_TEXT' and _d.GetText() == 'POWER OFF!' and _d.GetLayer() == pcbnew.F_SilkS:
        _bb = _d.GetBoundingBox()
        _d.Move(pcbnew.VECTOR2I(mm(47.6) - _bb.GetX(), mm(8.2) - _bb.GetY()))
        break
else:
    raise SystemExit('POWER OFF! label not found')
LAYERNAME = {F: 'F.Cu', I2: 'In2.Cu', B: 'B.Cu'}

def net(name):
    ni = b.FindNet(name)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); ni = b.FindNet(name)
    return ni
def add_track(layer, pts, netname, w):
    n = net(netname)
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(V(*a)); t.SetEnd(V(*c)); t.SetLayer(layer); t.SetWidth(mm(w)); t.SetNet(n); b.Add(t)
def add_via(x, y, netname, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(dia)); v.SetDrill(mm(drill)); v.SetNet(net(netname)); b.Add(v)
def pad(ref, num, which=0):
    f = next(f for f in b.GetFootprints() if f.GetReference() == ref)
    ps = [p for p in f.Pads() if p.GetNumber() == str(num)]
    p = ps[which]
    return (tomm(p.GetX()), tomm(p.GetY()))

# ---------------------------------------------------------------- 1. SW4 nets and old routes
sw = next(f for f in b.GetFootprints() if f.GetReference() == 'SW4')
sw.Reference().SetPosition(V(49.0, 12.4))     # keep clear of the moved 'POWER OFF!' label
for p in sw.Pads():
    if p.GetNumber() == '1': assert p.GetNetname() == 'BUCK_5V'; p.SetNet(net('SW_RUN'))
    if p.GetNumber() == '3': assert p.GetNetname() == 'VBUS_PD'; p.SetNet(net('SW_PGM'))
    if p.GetNumber() == '4': assert p.GetNetname() == '+5V'; p.SetNet(net('GND'))

def key(layer, a, c): return (layer, tuple(sorted([(round(a[0], 2), round(a[1], 2)), (round(c[0], 2), round(c[1], 2))])))
OLD_SEGS = {  # (net, layer, endpoints) of the routes that only served SW4 pads 1/3/4 (see add_sw.py)
    'BUCK_5V': [(F, (38.1, 26.8), (38.1, 23.7)), (F, (38.1, 23.7), (44.5, 17.3)), (F, (44.5, 17.3), (44.5, 15.0))],
    '+5V': [(F, (44.5, 7.3), (44.5, 7.0)), (F, (42.2, 9.6), (44.5, 7.3)), (F, (40.5, 9.6), (42.2, 9.6)), (F, (40.5, 9.7), (40.5, 9.6)),
            (B, (38.5, 11.7), (40.5, 9.7)), (B, (38.5, 20.1), (38.5, 11.7)), (B, (39.0, 20.6), (38.5, 20.1)), (B, (39.0, 23.9), (39.0, 20.6)),
            (F, (39.0, 28.5), (39.0, 23.9))],
    'VBUS_PD': [(B, (45.1, 11.6), (44.5, 11.0)), (B, (45.9, 11.6), (45.1, 11.6)), (B, (45.9, 16.4), (45.9, 11.6)), (B, (45.2, 16.4), (45.9, 16.4)),
                (B, (44.5, 17.1), (45.2, 16.4)), (B, (44.5, 20.2), (44.5, 17.1)),
                (I2, (41.1, 23.6), (44.5, 20.2)), (I2, (41.1, 27.6), (41.1, 23.6)), (I2, (39.0, 29.7), (41.1, 27.6)), (I2, (39.0, 31.1), (39.0, 29.7))]}
OLD_VIAS = {'+5V': [(40.5, 9.7), (39.0, 23.9)], 'VBUS_PD': [(44.5, 20.2)]}
want = {(n, key(l, a, c)) for n, lst in OLD_SEGS.items() for (l, a, c) in lst}
vwant = {(n, (round(x, 2), round(y, 2))) for n, lst in OLD_VIAS.items() for x, y in lst}
left, vleft, doomed = set(want), set(vwant), []
for t in b.GetTracks():          # collect first, remove afterwards (removing while iterating leaves stale SWIG objects)
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition(); k = (t.GetNetname(), (round(tomm(p.x), 2), round(tomm(p.y), 2)))
        if k in vwant: doomed.append(t); vleft.discard(k)
    else:
        s, e = t.GetStart(), t.GetEnd()
        k = (t.GetNetname(), key(t.GetLayer(), (tomm(s.x), tomm(s.y)), (tomm(e.x), tomm(e.y))))
        if k in want: doomed.append(t); left.discard(k)
assert not left, ('old segments not found', sorted(left))
assert not vleft, ('old vias not found', vleft)
for t in doomed: b.Remove(t)
print('removed old SW4 power copper items:', len(doomed))

# ---------------------------------------------------------------- 2. parts
PARTS = [  # ref, lib, name, rotation candidates, target (x, y)
    ('R92', 'Resistor_SMD', 'R_0603_1608Metric', (0, 90), (38.4, 18.0)),
    ('Q12', 'Package_TO_SOT_SMD', 'SOT-23', (0, 90, 180, 270), (36.2, 21.5)),
    ('Q11', 'Package_TO_SOT_SMD', 'SOT-23', (0, 90, 180, 270), (32.6, 21.5)),
    ('R91', 'Resistor_SMD', 'R_0603_1608Metric', (0, 90), (29.5, 21.5)),
    # PROGRAM group in the free strip along the top edge (x 16-38, y 2.3-8.4)
    ('Q14', 'Package_TO_SOT_SMD', 'SOT-23', (0, 90, 180, 270), (34.5, 5.2)),
    ('Q13', 'Package_TO_SOT_SMD', 'SOT-23', (0, 90, 180, 270), (31.0, 5.2)),
    ('R94', 'Resistor_SMD', 'R_0603_1608Metric', (0, 90), (37.4, 8.4)),
    ('R93', 'Resistor_SMD', 'R_0603_1608Metric', (0, 90), (37.4, 5.2)),
    ('Q15', 'Package_TO_SOT_SMD', 'SOT-23', (0, 90, 180, 270), (26.5, 5.2)),
    ('R95', 'Resistor_SMD', 'R_0603_1608Metric', (0, 90), (28.8, 5.2)),
    ('D12', 'Diode_SMD', 'D_SOD-123', (0, 90, 180, 270), (23.0, 5.2)),
]
BOM = {r['Reference']: r for r in __import__('csv').DictReader((K / 'bom-r5l.csv').open(encoding='utf8'))}

# obstacle raster for the placement search (F.Cu copper + all through hole pads + vias), 0.1 mm cells
X0, Y0, X1, Y1 = 14.0, 1.5, 50.5, 34.0
RES = 0.1
NX, NY = int((X1 - X0) / RES) + 1, int((Y1 - Y0) / RES) + 1
occ = bytearray(NX * NY)
def mark_rect(x0, y0, x1, y1, g=0.0):
    for j in range(max(0, int((y0 - g - Y0) / RES)), min(NY, int((y1 + g - Y0) / RES) + 1)):
        for i in range(max(0, int((x0 - g - X0) / RES)), min(NX, int((x1 + g - X0) / RES) + 1)):
            occ[j * NX + i] = 1
def mark_seg(a, c, w, g):
    n = max(1, int(math.hypot(c[0] - a[0], c[1] - a[1]) / (RES / 2)))
    for k in range(n + 1):
        x = a[0] + (c[0] - a[0]) * k / n; y = a[1] + (c[1] - a[1]) * k / n
        mark_rect(x - w / 2, y - w / 2, x + w / 2, y + w / 2, g)
CLR = 0.38   # copper clearance (0.2 DRC + margin for the router)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.IsOnLayer(F) or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            bb = p.GetBoundingBox(); mark_rect(tomm(bb.GetX()), tomm(bb.GetY()), tomm(bb.GetRight()), tomm(bb.GetBottom()), CLR)
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition(); r = 0.3
        mark_rect(tomm(p.x) - r, tomm(p.y) - r, tomm(p.x) + r, tomm(p.y) + r, CLR)
    elif t.GetLayer() == F:
        s, e = t.GetStart(), t.GetEnd()
        mark_seg((tomm(s.x), tomm(s.y)), (tomm(e.x), tomm(e.y)), tomm(t.GetWidth()), CLR)
# board outline margin
mark_rect(X0, Y0, X1, 2.2)
# existing courtyards (F.CrtYd): a new part's courtyard must not overlap them
cy_occ = bytearray(NX * NY)
def cy_rect(f):
    f.BuildCourtyardCaches()
    bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    if bb.GetWidth() == 0: return None
    return (tomm(bb.GetX()), tomm(bb.GetY()), tomm(bb.GetRight()), tomm(bb.GetBottom()))
def mark_cy(r, g=0.0):
    for j in range(max(0, int((r[1] - g - Y0) / RES)), min(NY, int((r[3] + g - Y0) / RES) + 1)):
        for i in range(max(0, int((r[0] - g - X0) / RES)), min(NX, int((r[2] + g - X0) / RES) + 1)):
            cy_occ[j * NX + i] = 1
for f in b.GetFootprints():
    r = cy_rect(f)
    if r: mark_cy(r)
    rf = f.Reference()                          # visible reference text of existing parts
    if rf.IsVisible() and rf.GetLayer() == pcbnew.F_SilkS:
        bb = rf.GetBoundingBox(); mark_cy((tomm(bb.GetX()), tomm(bb.GetY()), tomm(bb.GetRight()), tomm(bb.GetBottom())), 0.15)
for d in b.GetDrawings():                       # silkscreen labels already on the board (RUN/OFF/PGM, POWER OFF!, JP3 ...)
    if d.GetClass() == 'PCB_TEXT' and d.GetLayer() == pcbnew.F_SilkS:
        bb = d.GetBoundingBox(); mark_cy((tomm(bb.GetX()), tomm(bb.GetY()), tomm(bb.GetRight()), tomm(bb.GetBottom())), 0.25)
placed_boxes = []   # bboxes of parts placed so far (with routing gap)
GAP = 0.6           # keep this much between new parts: room for 0.25/0.5 mm routes

def load(lib, name):
    f = IO.FootprintLoad(str(SYS / (lib + '.pretty')), name)
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f
def pad_rects(f):
    out = []
    for p in f.Pads():
        bb = p.GetBoundingBox(); out.append((tomm(bb.GetX()), tomm(bb.GetY()), tomm(bb.GetRight()), tomm(bb.GetBottom())))
    return out
def fits(rects):
    for x0, y0, x1, y1 in rects:
        if x0 - CLR < X0 or y0 - CLR < Y0 or x1 + CLR > X1 or y1 + CLR > Y1: return False
        for j in range(int((y0 - Y0) / RES), int((y1 - Y0) / RES) + 1):
            for i in range(int((x0 - X0) / RES), int((x1 - X0) / RES) + 1):
                if occ[j * NX + i]: return False
    return True
def cy_fits(r):
    if r is None: return True
    for j in range(int((r[1] - Y0) / RES), int((r[3] - Y0) / RES) + 1):
        for i in range(int((r[0] - X0) / RES), int((r[2] - X0) / RES) + 1):
            if not (0 <= i < NX and 0 <= j < NY) or cy_occ[j * NX + i]: return False
    return True
def bbox_of(rects):
    return (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
def overlaps(bx, by):
    return not (bx[2] + GAP <= by[0] or by[2] + GAP <= bx[0] or bx[3] + GAP <= by[1] or by[3] + GAP <= bx[1])

new_fps = {}
for ref, lib, name, rots, (tx, ty) in PARTS:
    best = None
    for rot in rots:
        f = load(lib, name); f.SetOrientationDegrees(rot)
        for dx in [i * 0.1 for i in range(-100, 101)]:
            for dy in [j * 0.1 for j in range(-100, 101)]:
                d = math.hypot(dx, dy)
                if best and d >= best[0]: continue
                f.SetPosition(V(round(tx + dx, 1), round(ty + dy, 1)))
                rects = pad_rects(f)
                if not fits(rects): continue
                if not cy_fits(cy_rect(f)): continue
                bx = bbox_of(rects)
                if any(overlaps(bx, o) for o in placed_boxes): continue
                best = (d, round(tx + dx, 1), round(ty + dy, 1), rot, bx)
    assert best, ('no free spot for', ref)
    d, x, y, rot, bx = best
    f = load(lib, name); f.SetOrientationDegrees(rot); f.SetPosition(V(x, y))
    placed_boxes.append(bx)
    r_ = cy_rect(f)
    if r_: mark_cy(r_)
    f.SetReference(ref); f.SetValue(BOM[ref]['Value'])
    c = CONTRACT[ref]
    for p in f.Pads():
        nn = c['pins'].get(p.GetNumber())
        if nn: p.SetNet(net(nn))
    b.Add(f); new_fps[ref] = f
    rt = f.Reference()
    rt.SetLayer(pcbnew.F_SilkS); rt.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); rt.SetTextThickness(mm(0.12))
    f.Value().SetLayer(pcbnew.F_Fab)
    # reference text: first free side of the courtyard (not over silk labels, courtyards or other refs)
    cx_, cy_ = (r_[0] + r_[2]) / 2, (r_[1] + r_[3]) / 2
    done = False
    for off in (0.2, 0.8, 1.4, 2.0):
        for orient in (0, 90):
            tw, th = (len(ref) * 0.85 + 0.2, 1.0) if orient == 0 else (1.0, len(ref) * 0.85 + 0.2)
            for px, py in ((cx_, r_[1] - th / 2 - off), (cx_, r_[3] + th / 2 + off), (r_[0] - tw / 2 - off, cy_), (r_[2] + tw / 2 + off, cy_)):
                box = (px - tw / 2, py - th / 2, px + tw / 2, py + th / 2)
                if cy_fits(box):
                    rt.SetTextAngleDegrees(orient); rt.SetPosition(V(px, py)); rt.SetVisible(True); mark_cy(box)
                    done = True; break
            if done: break
        if done: break
    if not done: print('WARNING: no free spot for the reference text of', ref)
    print('placed', ref, 'at', x, y, 'rot', rot, 'moved', round(d, 1), 'mm from the target')

# ---------------------------------------------------------------- 3. routing
R = Router(b, (X0 - 1, Y0, X1, Y1), [F, I2, B], res=0.1, clr=0.2)
failed = []
def do(netname, w, terms, allowed=None):
    r = R.route(netname, w, terms, allowed)
    if r is None:
        failed.append(netname); print('UNROUTED', netname); return
    tracks, vias = r
    for layer, pts, ww in tracks:
        add_track(layer, pts, netname, ww); R.add_track(layer, pts, netname, ww)
    for x, y in vias:
        add_via(x, y, netname); R.add_via(x, y, netname)
    print('routed', netname, len(tracks), 'tracks', len(vias), 'vias')
def T(ref, num, layer=F, which=0):
    x, y = pad(ref, num, which); return (x, y, layer)
FB = [F, B]
exec(Path(__file__).with_name('loadsw_routes.py').read_text())
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(P))
print('saved', P.name, 'unrouted:', failed)
