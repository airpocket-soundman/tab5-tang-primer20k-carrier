"""Prepare reproducible 680ohm sources; PCB modification requires --apply-pcb.

Parent agent explicitly coordinates PCB writes after mechanical corrections.
Default execution updates generator/BOM/checker sources ONLY.
"""
from pathlib import Path
import hashlib
import json
import sys
import re

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
VARIANTS=('lite-a-dual','lite-b-barrel','lite-c-dnp')
MARKER='# BEGIN PoC parallel 680R qualification'
WRAPPER='''
# BEGIN PoC parallel 680R qualification
_build_before_series_680 = build
def build():
    cs = _build_before_series_680()
    changed = []
    for c in cs:
        if not c.ref.startswith('R') or len(c.pins) != 2:
            continue
        nets = set(c.pins.values())
        iso = next((n for n in nets if n and n.startswith('ISO_')), None)
        if iso and nets == {iso, 'F_' + iso[4:]}:
            assert c.value in ('33R','330R','680R') and not c.dnp, (c.ref, c.value)
            c.value = '680R'
            c.lcsc = 'C23228'
            c.comment = 'PoC 1MHz, 680ohm series damping; >=250ns DATA setup/hold, weak drive/SLOW; qualified distributed-RLC sensitivity'
            changed.append(c.ref)
    assert len(changed) == 15, changed
    return cs
# END PoC parallel 680R qualification
'''

def prepare(variant):
    folder=ROOT/'variants'/variant/'kicad'
    p=folder/'gen/design.py';s=p.read_text(encoding='utf-8-sig')
    s=re.sub(r"# BEGIN PoC parallel (?:330|680)R qualification.*?# END PoC parallel (?:330|680)R qualification\n?","",s,flags=re.S)
    if MARKER not in s:p.write_text(s.rstrip()+'\n'+WRAPPER,encoding='utf-8')
    p=folder/'gen/order_parts.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['parts']['680R|Resistor_SMD:R_0603_1608Metric']={'lcsc':'C23228','status':'Basic; 680ohm 0603 1%; recheck stock at order','url':'https://jlcpcb.com/partdetail/23955-0603WAF6800T5E/C23228'}
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
    p=folder/'sim/check_parallel_power.py';s=p.read_text(encoding='utf-8').replace("resistor.GetValue()=='33R'","resistor.GetValue()=='680R'").replace("resistor.GetValue()=='330R'","resistor.GetValue()=='680R'")
    p.write_text(s,encoding='utf-8')
    p=folder/'sim/make_pcb_report_page.py';s=p.read_text(encoding='utf-8').replace('→ 33Ω → Core','→ 680Ω → Core')
    p.write_text(s,encoding='utf-8')
    return {'variant':variant,'source_prepared':True,'PCB_written':False}

def geometry(board):
    import pcbnew
    copper=[]
    for t in board.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA):
            p=t.GetPosition();copper.append((t.m_Uuid.AsString(),t.GetNetname(),'via',p.x,p.y,t.GetWidth(pcbnew.F_Cu),t.GetDrillValue()))
        else:
            a,b=t.GetStart(),t.GetEnd();copper.append((t.m_Uuid.AsString(),t.GetNetname(),t.GetLayer(),a.x,a.y,b.x,b.y,t.GetWidth()))
    pads=[(f.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,p.GetSize().x,p.GetSize().y,p.GetOrientationDegrees()) for f in board.GetFootprints() for p in f.Pads()]
    return hashlib.sha256(json.dumps([sorted(copper),sorted(pads)],separators=(',',':')).encode()).hexdigest()

def apply(variant):
    import pcbnew
    path=ROOT/'variants'/variant/'kicad/tab5-fpga-carrier.kicad_pcb'
    before=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    b=pcbnew.LoadBoard(str(path));g=geometry(b);refs=[]
    for f in b.GetFootprints():
        if not f.GetReference().startswith('R'):continue
        nets={p.GetNetname() for p in f.Pads() if p.GetNetname()}
        iso=next((n for n in nets if n.startswith('ISO_')),None)
        if iso and nets=={iso,'F_'+iso[4:]}:
            assert f.GetValue() in ('33R','330R','680R') and not f.IsDNP()
            f.SetValue('680R');refs.append(f.GetReference())
    assert len(refs)==15,refs
    assert geometry(b)==g,'Value-only update modified physical geometry'
    pcbnew.SaveBoard(str(path),b)
    after=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    return dict(variant=variant,PCB_written=True,changed_refs=sorted(refs),sourcePCBhash_before=before,sourcePCBhash_after=after,geometry_hash=g,geometry_unchanged=True)

if __name__=='__main__':
    rows=[prepare(v) for v in VARIANTS]
    if '--apply-pcb' in sys.argv:rows=[apply(v) for v in VARIANTS]
    name='series-680-applied.json' if '--apply-pcb' in sys.argv else 'series-680-prepared.json'
    (HERE/name).write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rows,indent=2))
