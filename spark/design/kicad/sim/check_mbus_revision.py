"""Verify the real-Tab5 corner mapping and unchanged HDMI geometry."""
import json,subprocess
from pathlib import Path
import pcbnew
H=Path(__file__).resolve().parent;ROOT=H.parent.parent
b=pcbnew.LoadBoard(str(H.parent/'tab5-fpga-carrier.kicad_pcb'))
f=next(f for f in b.GetFootprints() if f.GetReference()=='J3');p={x.GetNumber():x for x in f.Pads()}
res=dict(previous_revision='bc0c4773ea76c73853146437912c04381d337ebc',user_confirmed_corners=True,corners={n:dict(x_mm=pcbnew.ToMM(p[n].GetPosition().x),y_mm=pcbnew.ToMM(p[n].GetPosition().y),net=p[n].GetNetname()) for n in ('1','2','29','30')},footprint=str(f.GetFPID().GetLibItemName()),tmds_unchanged={})
for name in ['tmds_roles.json','tmds_geom.json']:
 old=json.loads(subprocess.check_output(['git','show','bc0c477:kicad/sim/'+name],cwd=ROOT));new=json.loads((H/name).read_text())
 if name=='tmds_geom.json':
  for d in (old,new):
   for v in d.values():
    for k in ('segs','vias','pads'):
     if k in v:v[k]=sorted(v[k],key=lambda x:json.dumps(x,sort_keys=True))
 res['tmds_unchanged'][name]=old==new
res['ok']=all(res['tmds_unchanged'].values()) and res['corners']['1']['x_mm']<res['corners']['2']['x_mm'] and res['corners']['1']['net']=='GND' and res['corners']['29']['net']=='VIN' and res['corners']['2']['net']=='M_CLK' and not res['corners']['30']['net']
(H/'mbus_revision_check.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=1));raise SystemExit(0 if res['ok'] else 1)
