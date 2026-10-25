"""Cross-check HDMI revision actual PCB, XML, design, DNP and frozen essential copper."""
from pathlib import Path
import json,sys,subprocess,hashlib,gzip,collections,xml.etree.ElementTree as ET
import pcbnew
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];v=sys.argv[1];k=ROOT/'variants'/v/'kicad'
sys.path.insert(0,str(k/'gen'));import design
cs={c.ref:c for c in design.build()};b=pcbnew.LoadBoard(str(k/'tab5-fpga-carrier.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()}
xml=HERE/'models'/v/'final-schematic.net.xml';xml.parent.mkdir(exist_ok=True)
subprocess.run(['C:/Program Files/KiCad/10.0/bin/kicad-cli.exe','sch','export','netlist','--format','kicadxml','-o',str(xml),str(k/'tab5-fpga-carrier.kicad_sch')],check=True,capture_output=True)
nets={}
for n in ET.parse(xml).findall('./nets/net'):
 for node in n.findall('node'):nets[node.get('ref'),node.get('pin')]=n.get('name').lstrip('/')
errors=[]
for ref,c in cs.items():
 f=fps[ref]
 if f.GetValue()!=c.value or f.IsDNP()!=c.dnp:errors.append([ref,'value/DNP'])
 for pin,net in c.pins.items():
  if net is not None and nets.get((ref,pin))!=net:errors.append([ref,pin,'XML',net,nets.get((ref,pin))])
 for p in f.Pads():
  if not p.GetNumber():continue
  expected=(c.pads or c.pins).get(p.GetNumber())
  if p.GetNumber() in ('MP','SH'):expected='GND'
  if p.GetNetname()!=(expected or ''):errors.append([ref,p.GetNumber(),'PCB',expected,p.GetNetname()])
def copper(board):
 r=collections.Counter()
 for t in board.GetTracks():
  net=t.GetNetname()
  if net=='GND' or net in ('HDMI_SDA','HDMI_SCL','HDMI_5V','HDMI_HPD','F_HPD','HPD_B','HPD_BUF'):continue
  if isinstance(t,pcbnew.PCB_VIA):key=('v',net,t.GetPosition().x,t.GetPosition().y,t.GetWidth(pcbnew.F_Cu),t.GetDrillValue())
  else:key=('t',net,t.GetLayer(),tuple(sorted(((t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)))),t.GetWidth())
  r[key]+=1
 return r
base=Path('D:/tmp/hdmi-cad-revision')/v/'kicad/input-pre-hdmi.kicad_pcb'
# Early prototypes predate baseline persistence: materialize exact compressed snapshot.
base.write_bytes(gzip.decompress((HERE/'cad-baseline'/(v+'.kicad_pcb.gz')).read_bytes()))
old=copper(pcbnew.LoadBoard(str(base)));new=copper(b);removed=old-new
checks={'all_model_XML_PCB_pin_nets_values_DNP':not errors,'all_essential_power_parallel_original_TMDS_copper_preserved':not removed,'added_HPD_parts_correct_population':all(fps[r].IsDNP()==(v=='lite-c-dnp') for r in ('Q5','R51','R52','C24'))}
r={'variant':v,'source_raw_sha256':hashlib.sha256((k/'tab5-fpga-carrier.kicad_pcb').read_bytes()).hexdigest(),'ok':all(checks.values()),'checks':checks,'errors':errors,'removed_essential_copper_items':len(removed),'scope':'Connectivity/population/copper provenance; no assertion of firmware or hardware operation'}
(HERE/'models'/v/'cad-crosscheck.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=1));raise SystemExit(0 if r['ok'] else 1)
