"""Place D1 bias resistors in the post-ESD gaps, preserving the main pairs.

Run with KiCad Python on the routed board. Also used by make_pcb after its
coarse-grid route. The router stages these parts in the original open area;
its inflated pad masks cannot represent the narrow but DRC-legal final gaps.
"""
from pathlib import Path
from copy import copy
import json
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
FPDIR = Path('C:/Program Files/KiCad/10.0/share/kicad/footprints')
TARGETS = {'R30': ('HDMI_D1P_C', 16.75, 17.335),
           'R31': ('HDMI_D1N_C', 18.25, 17.665)}
_KEEPALIVE = []  # KiCad 10 SWIG objects removed from a board must survive saving.


def routing_components(comps):
    staged = []
    for c in comps:
        if c.ref in TARGETS:
            c = copy(c)
            c.fp = 'Resistor_SMD:R_0603_1608Metric'
            c.pos = (104.6 if c.ref == 'R30' else 106.3, 10.2)
            c.rot = 90
        staged.append(c)
    return staged


def apply(board, replacements=None):
    roles_path = ROOT/'sim/tmds_roles.json'
    roles = json.loads(roles_path.read_text())
    _KEEPALIVE.extend(board.GetTracks())
    _KEEPALIVE.extend(board.GetFootprints())
    for ref, (net, y, tap_y) in TARGETS.items():
        old = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        if (str(old.GetFPID().GetLibItemName()) == 'R_0402_1005Metric' and
            abs(pcbnew.ToMM(old.GetPosition().x)-110.3)<1e-6 and
            abs(pcbnew.ToMM(old.GetPosition().y)-y)<1e-6):
            continue  # repeated finalization preserves the already checked geometry
        branch = roles[net]['branch']
        # Remove only tracks represented by the old branch role, never the main.
        edges = []
        for ly, points, width in branch:
            for a, b in zip(points, points[1:]):
                edges.append((['F.Cu','In2.Cu','B.Cu'][ly], a, b, width))
        for t in list(board.GetTracks()):
            if t.GetNetname() != net:
                continue
            if isinstance(t, pcbnew.PCB_VIA):
                pos = [pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)]
                if not any(sum((u-v)**2 for u,v in zip(pos,point))<1e-8
                           for _,points,_ in branch for point in points):
                    raise RuntimeError('Unexpected D1 via outside a bias branch')
                board.RemoveNative(t)
                continue
            a = [pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y)]
            b = [pcbnew.ToMM(t.GetEnd().x), pcbnew.ToMM(t.GetEnd().y)]
            def near(p, q): return sum((u-v)**2 for u,v in zip(p,q)) < 1e-10
            if any(board.GetLayerName(t.GetLayer()) == ly and
                   abs(pcbnew.ToMM(t.GetWidth())-w)<1e-6 and
                   ((near(a,c) and near(b,d)) or (near(a,d) and near(b,c)))
                   for ly,c,d,w in edges):
                board.RemoveNative(t)
        fp = replacements[ref] if replacements else pcbnew.FootprintLoad(str(FPDIR/'Resistor_SMD.pretty'), 'R_0402_1005Metric')
        fp.SetReference(ref)
        fp.SetValue(old.GetValue())
        fp.SetPath(old.GetPath())
        fp.SetUuid(old.m_Uuid)
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(110.3), pcbnew.FromMM(y)))
        fp.SetOrientationDegrees(0)
        for pad in fp.Pads():
            pad.SetNet(board.FindNet(net if pad.GetNumber() == '1' else 'GND'))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        board.RemoveNative(old)
        board.Add(fp)
        def point(x, yy): return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(yy))
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(point(109.79,y)); t.SetEnd(point(109.79,tap_y))
        t.SetWidth(pcbnew.FromMM(.127)); t.SetLayer(pcbnew.F_Cu)
        t.SetNet(board.FindNet(net)); board.Add(t)
        roles[net]['branch'] = [[0, [[109.79,y],[109.79,tap_y]], .127]]
        via = pcbnew.PCB_VIA(board)
        # Keep an ordinary drilled via out of the 0402 solder-paste land.
        # The short ground return fits the same gap, avoiding via-in-pad fill.
        via.SetPosition(point(111.5,y)); via.SetWidth(pcbnew.FromMM(.6))
        via.SetDrill(pcbnew.FromMM(.3)); via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(board.FindNet('GND')); board.Add(via)
        ground = pcbnew.PCB_TRACK(board)
        ground.SetStart(point(110.81,y)); ground.SetEnd(point(111.5,y))
        ground.SetWidth(pcbnew.FromMM(.2)); ground.SetLayer(pcbnew.F_Cu)
        ground.SetNet(board.FindNet('GND')); board.Add(ground)
    roles_path.write_text(json.dumps(roles), encoding='utf-8')


if __name__ == '__main__':
    path = ROOT/'tab5-fpga-carrier.kicad_pcb'
    replacements = {ref: pcbnew.FootprintLoad(str(FPDIR/'Resistor_SMD.pretty'), 'R_0402_1005Metric') for ref in TARGETS}
    board = pcbnew.LoadBoard(str(path))
    apply(board, replacements)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)
