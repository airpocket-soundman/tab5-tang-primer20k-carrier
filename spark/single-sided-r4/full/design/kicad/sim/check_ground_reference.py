"""Check actual In1 filled GND beneath all TMDS main/escape/strap tracks."""
import json,math
from pathlib import Path
import pcbnew
HERE=Path(__file__).resolve().parent
b=pcbnew.LoadBoard(str(HERE.parent/'tab5-fpga-carrier.kicad_pcb'))
roles=json.loads((HERE/'tmds_roles.json').read_text())
z=next(z for z in b.Zones() if z.IsOnLayer(pcbnew.In1_Cu) and z.GetNetname()=='GND')
poly=z.GetFilledPolysList(pcbnew.In1_Cu)
missing=[];samples=0
for net,r in roles.items():
 for role in ('main','stub','strap'):
  for layer,pts,width in r.get(role,[]):
   if layer!=0:raise ValueError('TMDS main geometry left front layer')
   for a,c in zip(pts,pts[1:]):
    n=max(1,math.ceil(math.dist(a,c)/.25))
    for i in range(n+1):
     p=pcbnew.VECTOR2I(pcbnew.FromMM(a[0]+(c[0]-a[0])*i/n),pcbnew.FromMM(a[1]+(c[1]-a[1])*i/n));samples+=1
     if not poly.Contains(p):missing.append(dict(net=net,role=role,x=pcbnew.ToMM(p.x),y=pcbnew.ToMM(p.y)))
out=dict(ok=not missing,samples=samples,step_mm=.25,scope='Main/escape/strap centreline projection onto actual filled In1 GND. Resistor branches/via antipads excluded. Does not prove full return-current or EM performance.',missing_samples=missing)
(HERE/'ground_reference_check.json').write_text(json.dumps(out,indent=2))
print('TMDS main GND reference',out['ok'],'samples',samples)
raise SystemExit(0 if out['ok'] else 1)
