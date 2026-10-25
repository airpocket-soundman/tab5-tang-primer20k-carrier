"""Reproducible local C update of the preserved, routed release (KiCad Python).

No routing change to the bus or HDMI; replace only socket/L1/U3 and add the
feedback trim and a short LDO supply connection. DRC is a separate mandatory gate.
"""
import hashlib
import json
from pathlib import Path
import pcbnew
import design

ROOT = Path(__file__).resolve().parents[4]
KICAD = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'kicad/tab5-fpga-carrier.kicad_pcb'
SOURCE_HASH = '3f18d19c61bfdef88fbb5dfbf2ecf2d14429fea04aac2277421b07a06ec30d91'
FPDIR = Path('C:/Program Files/KiCad/10.0/share/kicad/footprints')
KEEP = []
mm=pcbnew.FromMM
def V(x,y): return pcbnew.VECTOR2I(mm(x),mm(y))

def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH, 'Preserved PCB changed; review update source first'
    board=pcbnew.LoadBoard(str(SOURCE))
    board.GetTitleBlock().SetTitle('Tab5 x Tang Primer 20K carrier - Lite C, barrel / HDMI+PD DNP')
    board.GetTitleBlock().SetRevision('lite-c-dnp-0.1')
    board.GetTitleBlock().SetDate('2026-10-25')
    fps={f.GetReference(): f for f in board.GetFootprints()}
    comps={c.ref:c for c in design.build()}
    if not board.FindNet('FB_TRIM'):
        board.Add(pcbnew.NETINFO_ITEM(board,'FB_TRIM'))
    for ref in ('J4','L1','U3','C10','C11','R49','R50'):
        c=comps[ref]
        lib,name=c.fp.split(':')
        folder=KICAD/'lib/carrier.pretty' if lib=='carrier' else FPDIR/(lib+'.pretty')
        f=pcbnew.FootprintLoad(str(folder),name)
        assert f is not None,c.fp
        f.SetFPID(pcbnew.LIB_ID(lib,name))
        old=fps.get(ref)
        if old:
            f.SetUuid(old.m_Uuid)
            f.SetPath(old.GetPath())
            f.SetPosition(old.GetPosition())
            f.SetOrientationDegrees(old.GetOrientationDegrees())
        if not old or ref in ('U3','C10','C11'):
            f.SetPosition(V(*c.pos));f.SetOrientationDegrees(c.rot)
        f.SetReference(ref);f.SetValue(c.value);f.SetDNP(c.dnp)
        for p in f.Pads():
            net=c.pins.get(p.GetNumber())
            if p.GetNumber()=='MP':net='GND'
            if net:p.SetNet(board.FindNet(net))
        f.Reference().SetVisible(False);f.Value().SetVisible(False)
        if old:KEEP.append(old);board.RemoveNative(old)
        board.Add(f);fps[ref]=f
    for ref,c in comps.items():
        f=fps[ref];f.SetValue(c.value);f.SetDNP(c.dnp)
    # The old C10 0.1mm terminal spur is redundant after relocating the cap.
    # Remove that spur only; the supplying through-via and power tree remain.
    for t in list(board.GetTracks()):
        if t.m_Uuid.AsString()=='52e79924-7abb-46e5-a613-5654b8b17a0e':
            assert t.GetNetname()=='+5V' and pcbnew.ToMM(t.GetLength())<.101
            KEEP.append(t);board.RemoveNative(t)
    def track(net,pts,w=.25,layer=pcbnew.F_Cu):
        for a,b in zip(pts,pts[1:]):
            t=pcbnew.PCB_TRACK(board);t.SetStart(V(*a));t.SetEnd(V(*b));t.SetWidth(mm(w));t.SetLayer(layer);t.SetNet(board.FindNet(net));board.Add(t)
    def via(net,xy):
        v=pcbnew.PCB_VIA(board);v.SetPosition(V(*xy));v.SetWidth(mm(.6));v.SetDrill(mm(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(board.FindNet(net));board.Add(v)
    track('GND',[(60.8,6.7),(60.85,7.1)],.2)
    track('GND',[(58.6,7.025),(59.5,7.025),(60.85,7.1)],.3)
    track('+3V3',[(58.6,9.975),(59.7,9.975),(60.85,9)],.3)
    track('+5V',[(62.725,8.05),(63.8,8.05),(64.3,7.55),(64.3,7.2)],.25)
    via('+5V',(64.3,7.2))
    track('+5V',[(63.525,5.5),(64.3,5.5),(64.3,7.2)],.3)
    track('GND',[(66.475,5.5),(67.9,5.5)],.3)
    via('GND',(67.9,5.5))
    track('+5V',[(64.3,7.2),(64.3,11.3),(62.3,11.3)],.25,pcbnew.B_Cu)
    track('BUCK_FB',[(20,68.325),(18,68.325),(15.675,68.325),(15.675,69.5)],.2)
    track('FB_TRIM',[(17.325,69.5),(18.5,69.5),(18.5,71),(15.675,71),(15.675,72.5)],.2)
    track('GND',[(17.325,72.5),(18.5,72.5)],.25)
    via('GND',(18.5,72.5))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(KICAD/'tab5-fpga-carrier.kicad_pcb'),board)
    (KICAD/'sim/local-update.json').write_text(json.dumps({'source_pcb_sha256':SOURCE_HASH,'source_release':'d93af0b','strategy':'local update preserving original bus and HDMI routing; local LDO/decoupling and feedback paths only','replaced_footprints':['J4','L1','U3'],'relocated_footprints':['C10','C11'],'removed_redundant_C10_spur_mm':.1,'new_footprints':['R49','R50'],'mandatory_next_gate':'KiCad DRC and actual PCB connectivity'},indent=2)+'\n')
    print('Saved local-update lite C PCB with',len(fps),'footprints')

if __name__=='__main__':main()
