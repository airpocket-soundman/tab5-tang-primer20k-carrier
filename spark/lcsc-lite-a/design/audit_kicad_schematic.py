from pathlib import Path
import xml.etree.ElementTree as ET,json,sys
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'kicad/gen'));import design
tree=ET.parse(H/'kicad/sim/schematic-netlist.xml');nets={}
for net in tree.findall('.//nets/net'):
 for node in net.findall('node'):nets[(node.attrib['ref'],node.attrib['pin'])]=net.attrib['name']
errors=[];count=0
for c in design.build():
 for pin,net in c.pins.items():
  if net is None:continue
  count+=1;actual=nets.get((c.ref,pin))
  # Root-sheet local labels are serialized as /NAME; model has NAME.
  if actual and actual.startswith('/') and actual.count('/')==1:actual=actual[1:]
  if actual!=net:errors.append({'ref':c.ref,'pin':pin,'expected':net,'actual':actual})
report={'ok':not errors,'connected_pins_checked':count,'errors':errors}
(H/'kicad/sim/schematic-model-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if report['ok'] else 1)
