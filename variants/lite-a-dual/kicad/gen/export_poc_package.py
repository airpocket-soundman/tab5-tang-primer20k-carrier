"""Export consistent Gerber/drill/BOM/CPL candidate; run with KiCad Python."""
import csv,hashlib,json,subprocess,sys,zipfile,tempfile
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[2];CLI=Path(sys.executable).parent/'kicad-cli.exe'
PCB=ROOT/'kicad/tab5-fpga-carrier.kicad_pcb';OUT=ROOT/'manufacturing/lite-a-dual-2026-10-25'
MANUAL={'J1','J3','J5','SW1','SW2','SW3','JP1'}
def run(*args):subprocess.run([str(CLI),*map(str,args)],check=True)
def main():
 OUT.mkdir(parents=True,exist_ok=True);g=OUT/'gerbers';g.mkdir(exist_ok=True)
 checks=json.loads((ROOT/'kicad/sim/parallel_power_check.json').read_text())
 assert checks['ok'] and any(r['name']=='M5Bus_confirmed_left_pin1' and r['ok'] for r in checks['checks'])
 drc=json.loads((ROOT/'kicad/sim/drc_r3.json').read_text())
 assert not drc['violations'] and not drc['unconnected_items']
 b=pcbnew.LoadBoard(str(PCB));fps={f.GetReference():f for f in b.GetFootprints()}
 run('pcb','export','gerbers','-l','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts','--subtract-soldermask','--use-drill-file-origin','-o',str(g)+'/',PCB)
 run('pcb','export','drill','--drill-origin','plot','--excellon-separate-th','--generate-report','-o',str(g)+'/',PCB)
 run('pcb','export','pos','--format','csv','--units','mm','--exclude-dnp','--use-drill-file-origin','-o',OUT/'kicad-position.csv',PCB)
 run('pcb','export','ipcd356','-o',OUT/'connectivity.d356',PCB)
 # Render a clean assembly-only temporary copy: one reference per part, no values.
 with tempfile.TemporaryDirectory(prefix='carrier-assembly-') as td:
  draw=pcbnew.LoadBoard(str(PCB))
  for f in draw.GetFootprints():
   f.Value().SetLayer(pcbnew.Dwgs_User)
   r=f.Reference();r.SetVisible(True);r.SetLayer(pcbnew.B_Fab if f.IsFlipped() else pcbnew.F_Fab)
   r.SetPosition(f.GetPosition());r.SetTextAngle(pcbnew.EDA_ANGLE(0,pcbnew.DEGREES_T));r.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(.65),pcbnew.FromMM(.65)));r.SetTextThickness(pcbnew.FromMM(.10))
   for item in f.GraphicalItems():
    if item.GetClass() in ('PCB_TEXT','PCB_FIELD'):item.SetLayer(pcbnew.Dwgs_User)
   r.SetLayer(pcbnew.B_Fab if f.IsFlipped() else pcbnew.F_Fab)
   label_positions={'J3':(51.5,40),'J1':(35,16),'JP1':(62,71.5)}
   if f.GetReference() in label_positions:
    x,y=label_positions[f.GetReference()];r.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
  dp=Path(td)/'assembly.kicad_pcb';pcbnew.SaveBoard(str(dp),draw)
  for side,layer in [('top','F.Fab'),('bottom','B.Fab')]:
   args=['pcb','export','svg','-l',layer+',Edge.Cuts','--mode-single','--black-and-white','--fit-page-to-board','--exclude-drawing-sheet','--crossout-DNP-footprints-on-fab-layers','-o',OUT/('assembly-'+side+'.svg'),dp]
   if side=='bottom':args.insert(3,'--mirror')
   run(*args)
 bom=list(csv.DictReader((ROOT/'kicad/bom.csv').open(encoding='utf8',newline='')));refs=set();rows=[];manual=[]
 for r in bom:
  rr=r['Refs'].split(',')
  if r['DNP']:continue
  if all(x.startswith('H') or x in MANUAL for x in rr):manual.append([r['Refs'],r['Value'],r['Footprint'],'manual / not in PCBA']);continue
  assert r['LCSC'],r
  assert all(fps[x].GetValue()==r['Value'] and not fps[x].IsDNP() for x in rr),r
  rows.append([r['Value'],r['Refs'],r['Footprint'],r['LCSC']]);refs.update(rr)
 def write(name,header,rows):
  with (OUT/name).open('w',encoding='utf8',newline='') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
 write('jlc-bom.csv',['Comment','Designator','Footprint','LCSC Part #'],rows)
 pos=list(csv.DictReader((OUT/'kicad-position.csv').open(encoding='utf8',newline='')))
 cpl=[[r['Ref'],r['PosX'],r['PosY'],r['Side'],r['Rot']] for r in pos if r['Ref'] in refs]
 assert {r[0] for r in cpl}==refs and len(cpl)==len(refs)
 assert not {'J6','J7','J8'}.intersection(refs),'PMOD/GPIO pin sockets must remain outside PCBA'
 assert 'J4' in refs,'Core socket must be assembled by PCBA'
 write('jlc-cpl.csv',['Designator','Mid X','Mid Y','Layer','Rotation'],cpl)
 write('manual-assembly.csv',['Refs','Value','Footprint','Action'],manual)
 write('dnp.csv',['Refs','Value','Footprint'],[[r['Refs'],r['Value'],r['Footprint']] for r in bom if r['DNP']])
 for r in cpl:assert 0<=float(r[1])<=99 and 0<=float(r[2])<=78,r
 with zipfile.ZipFile(OUT/'gerbers.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(g.iterdir()):z.write(p,p.name)
 report=dict(status='PoC design-checked manufacturing candidate lite A; socket procurement/fixture and assembly preview require supplier confirmation',pcba_components=len(refs),pcba_bom_rows=len(rows),bom_cpl_equal=True,origin_mm=[28,79],board_dimensions_mm=[99,78],cpl_coordinates='KiCad drill/place origin, +X right +Y up; bottom only manual J3; rotation is KiCad convention, confirm manufacturer preview',manual_refs=sorted(MANUAL),source_pcb_sha256=hashlib.sha256(PCB.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='package-check.json'})
 (OUT/'package-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=1))
if __name__=='__main__':main()
