"""Prototype lower-profile HDMI in a temporary copy, preserving main routes.

Writes a temporary copy only. C receives the same retained topology, with HDMI parts DNP.
"""
from pathlib import Path
import json
import shutil
import gzip
import hashlib
import sys
import pcbnew

ROOT=Path(__file__).resolve().parents[3]
variant=sys.argv[1]
source=ROOT/'variants'/variant/'kicad'
target=Path('D:/tmp/hdmi-cad-revision')/variant/'kicad'
target.mkdir(parents=True,exist_ok=True)
for name in ('tab5-fpga-carrier.kicad_pro','fp-lib-table','sym-lib-table'):
    shutil.copyfile(source/name,target/name)
shutil.copytree(source/'lib',target/'lib',dirs_exist_ok=True)
shutil.copytree(source/'gen',target/'gen',dirs_exist_ok=True)
for name in ('tab5-fpga-carrier.kicad_sch','bom.csv','core_pin_assignment.csv'):
    shutil.copyfile(source/name,target/name)
(target/'sim').mkdir(exist_ok=True)
baseline=ROOT/'variants/simulation/hdmi/cad-baseline'
current_sha=hashlib.sha256((source/'tab5-fpga-carrier.kicad_pcb').read_bytes()).hexdigest()
base_sha=hashlib.sha256(gzip.decompress((baseline/(variant+'.kicad_pcb.gz')).read_bytes())).hexdigest()
allowed={base_sha}
adoption=source/'sim/hdmi-revision-adoption.json'
if adoption.exists():allowed.add(json.loads(adoption.read_text())['adopted_raw_sha256'])
assert current_sha in allowed,'Current PCB has edits beyond the qualified snapshot; audit and refresh baseline instead of overwriting them'
roles=json.loads((baseline/(variant+'-roles.json')).read_text(encoding='utf-8'))
input_pcb=target/'input-pre-hdmi.kicad_pcb'
input_pcb.write_bytes(gzip.decompress((baseline/(variant+'.kicad_pcb.gz')).read_bytes()))
board=pcbnew.LoadBoard(str(input_pcb))
fps={f.GetReference():f for f in board.GetFootprints()}
keep=[]

def xy(v):return (pcbnew.ToMM(v.x),pcbnew.ToMM(v.y))
def point(p):return pcbnew.VECTOR2I(*(pcbnew.FromMM(x) for x in p))
def wire(net,pts,width=.127,role=None):
    for a,b in zip(pts,pts[1:]):
        if sum((a[i]-b[i])**2 for i in range(2))<1e-12:continue
        t=pcbnew.PCB_TRACK(board);t.SetStart(point(a));t.SetEnd(point(b));t.SetNet(board.FindNet(net));t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(width));board.Add(t)
    if role:roles[net][role].append([0,[list(p) for p in pts],width])
def replacement(ref,lib,name):
    old=fps[ref];new=pcbnew.FootprintLoad(str(lib),name)
    new.SetReference(ref);new.SetValue(old.GetValue());new.SetPosition(old.GetPosition());new.SetOrientationDegrees(old.GetOrientationDegrees());new.SetDNP(old.IsDNP());new.SetPath(old.GetPath());new.SetUuid(old.m_Uuid)
    new.Reference().SetVisible(False);new.Value().SetVisible(False)
    board.RemoveNative(old);keep.append(old);board.Add(new);fps[ref]=new
    return old,new
if True:
    for i in range(12,20):
        old,new=replacement(f'C{i}',Path('C:/Program Files/KiCad/10.0/share/kicad/footprints/Capacitor_SMD.pretty'),'C_0402_1005Metric')
        op={p.GetNumber():p for p in old.Pads()}
        for p in new.Pads():
            oldpad=op[p.GetNumber()];p.SetNet(oldpad.GetNet());net=p.GetNetname()
            wire(net,[xy(oldpad.GetPosition()),xy(p.GetPosition())],.2,'main')
    old,new=replacement('U6',source/'lib/carrier.pretty','DFN2510-10L_RCLAMP0524P')
    new.SetValue('RCLAMP0524P')
    oldpads={p.GetNumber():p for p in old.Pads()}
    maps={'1':'HDMI_SDA','10':'HDMI_SDA','2':'HDMI_5V','9':'HDMI_5V','4':'HDMI_SCL','7':'HDMI_SCL','5':'HDMI_HPD','6':'HDMI_HPD','3':'GND','8':'GND'}
    np={p.GetNumber():p for p in new.Pads()}
    for n,p in np.items():p.SetNet(board.FindNet(maps[n]))
    for a,b in (('1','10'),('2','9'),('4','7'),('5','6'),('3','8')):wire(maps[a],[xy(np[a].GetPosition()),xy(np[b].GetPosition())],.2)
    # Remove the old sideband topology before routing the new lands. All TMDS
    # copper and parallel paths remain immutable.
    reroute={'HDMI_SDA','HDMI_SCL','HDMI_5V','HDMI_HPD','F_HPD'}
    for t in list(board.GetTracks()):
        q=xy(t.GetPosition())
        if t.GetNetname() in reroute or (t.GetNetname()=='GND' and 104<q[0]<110 and 23<q[1]<27):board.RemoveNative(t)
    # Restore independent-channel copper straps after old topology removal.
    for a,b in (('1','10'),('2','9'),('4','7'),('5','6'),('3','8')):wire(maps[a],[xy(np[a].GetPosition()),xy(np[b].GetPosition())],.2)
    board.Add(pcbnew.NETINFO_ITEM(board,'HPD_B'));board.Add(pcbnew.NETINFO_ITEM(board,'HPD_BUF'))
    for ref,pin,net in [('R40','2','HPD_B'),('R41','1','HPD_B')]:
        next(p for p in fps[ref].Pads() if p.GetNumber()==pin).SetNet(board.FindNet(net))
    fps['R40'].SetValue('47k');fps['R41'].SetValue('100k')
    def add(ref,lib,name,pos,rot,value,nets):
        f=pcbnew.FootprintLoad(str(lib),name);f.SetReference(ref);f.SetValue(value);f.SetPosition(point(pos));f.SetOrientationDegrees(rot);f.SetDNP(variant=='lite-c-dnp');f.Reference().SetVisible(False);f.Value().SetVisible(False);board.Add(f);fps[ref]=f
        for p in f.Pads():p.SetNet(board.FindNet(nets[p.GetNumber()]))
    syslib=Path('C:/Program Files/KiCad/10.0/share/kicad/footprints')
    add('Q5',syslib/'Package_TO_SOT_SMD.pretty','SOT-23',(61,55),0,'MMBT3904',{'1':'HPD_B','2':'GND','3':'HPD_BUF'})
    add('R51',syslib/'Resistor_SMD.pretty','R_0603_1608Metric',(60,58),0,'47k',{'1':'+3V3','2':'HPD_BUF'})
    add('C24',syslib/'Capacitor_SMD.pretty','C_0603_1608Metric',(65,53) if variant=='lite-c-dnp' else (65,55),90 if variant=='lite-c-dnp' else 0,'100n',{'1':'HPD_BUF','2':'GND'})
    add('R52',syslib/'Resistor_SMD.pretty','R_0603_1608Metric',(68,55),0,'10k',{'1':'HPD_BUF','2':'F_HPD'})
    sys.path.insert(0,str(source/'gen'));import route_pcb as rt
    rt.GRID=.1
    r=rt.Router(board,*rt.design.BOARD);r.load(rt.design.BOARD);r.max_exp=300000
    layers={pcbnew.F_Cu:0,pcbnew.In2_Cu:1,pcbnew.B_Cu:2}
    for t in board.GetTracks():
        n=r.nid(t.GetNetname())
        if isinstance(t,pcbnew.PCB_VIA):
            for l in range(3):r.stamp_disc(l,*xy(t.GetPosition()),n,pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+rt.CLR+rt.TW/2)
        elif t.GetLayer() in layers:r.stamp_path(layers[t.GetLayer()],[xy(t.GetStart()),xy(t.GetEnd())],n,pcbnew.ToMM(t.GetWidth()))
    r.base=[o.copy() for o in r.occ]
    r.pads['+3V3']=[x for x in r.pads['+3V3'] if x[3] in ('R51.1','R37.1')]
    r.add_escape_stubs({'J4.30':(2.4,lambda x,y:1),'J5.15':(2.6,lambda x,y:-1),'J5.16':(2.6,lambda x,y:-1),'J5.18':(2.6,lambda x,y:-1),'J5.19':(2.6,lambda x,y:-1)})
    if variant=='lite-c-dnp':r.stitch_gnd(lambda ref:ref.split('.')[0] in ('Q5','C24','U6'),limit=100)
    failed=[]
    for net in ['HPD_B','HPD_BUF','F_HPD','HDMI_HPD','HDMI_SDA','HDMI_SCL','HDMI_5V','+3V3']:
        ok=r.route_net(net,rt.TW,12);print(net,ok,flush=True)
        if not ok:failed.append(net)
    if variant!='lite-c-dnp':r.stitch_gnd(lambda ref:ref.split('.')[0] in ('Q5','C24','U6'),limit=80)
    for net,l,pts,w in r.perm+r.tracks:
        for a,b in zip(pts,pts[1:]):
            t=pcbnew.PCB_TRACK(board);t.SetStart(point(a));t.SetEnd(point(b));t.SetNet(board.FindNet(net));t.SetLayer([pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu][l]);t.SetWidth(pcbnew.FromMM(w));board.Add(t)
    def via(net,pos):
        v=pcbnew.PCB_VIA(board);v.SetPosition(point(pos));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(board.FindNet(net));board.Add(v)
    for net,x,y in set(r.vias):via(net,(x,y))
    (target/'prototype_status.json').write_text(json.dumps({'failed_routes':failed,'source_raw_sha256':__import__('hashlib').sha256((source/'tab5-fpga-carrier.kicad_pcb').read_bytes()).hexdigest()},indent=2))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(target/'tab5-fpga-carrier.kicad_pcb'),board)
(target/'sim/tmds_roles.json').write_text(json.dumps(roles)+'\n',encoding='utf-8')
print(target)
