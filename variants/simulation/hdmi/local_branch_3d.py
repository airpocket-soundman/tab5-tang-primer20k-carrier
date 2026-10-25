"""Bounded openEMS MSL-port local D1 bias-branch model, not a socket model.

Geometry: carrier h=.2104mm, copper35um, w=.2/g=.13; two .585mm
outward .127mm branches, 0402 lands .54x.64, 1.02mm pad pitch,
510ohm ideal resistor, .69mm ground stub to .3mm drilled via.
The ideal solid PEC ground-via equivalent terminates at the first plane; plating
resistance, the drill interior, full 1.6mm via stub,
soldermask, solder and resistor internal parasitics are not included.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
import numpy as np

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--package',type=Path,default=Path('D:/tmp/meos-openems/package/openEMS'))
ap.add_argument('--work',type=Path,required=True)
ap.add_argument('--mesh',type=float,default=.025)
ap.add_argument('--zdiv',type=int,default=12)
ap.add_argument('--branch',action='store_true')
ap.add_argument('--postprocess',action='store_true')
a=ap.parse_args()
pkg=str(a.package.resolve())
os.environ['CSXCAD_INSTALL_PATH']=pkg
os.environ['OPENEMS_INSTALL_PATH']=pkg
_dll=os.add_dll_directory(pkg)
from CSXCAD import ContinuousStructure
from openEMS import openEMS

wd=a.work.resolve();wd.mkdir(parents=True,exist_ok=True)
fd=openEMS(NrTS=160000,EndCriteria=1e-5)
fd.SetGaussExcite(3e9,3e9)
fd.SetBoundaryCond(['PML_8','PML_8','MUR','MUR','PEC','MUR'])
cs=ContinuousStructure();fd.SetCSX(cs)
mesh=cs.GetGrid();mesh.SetDeltaUnit(1e-3)
h=.2104;t=.035;w=.2;gap=.13;fine=a.mesh
centres=[-(w+gap)/2,(w+gap)/2]
xlines=[-15,-10,-8,0,8,10,15]
for edge in (-.0635,.0635,-.27,.27,.75,1.29,1.71-.175,1.71+.175):
    xlines.extend((edge-fine/3,edge+2*fine/3))
mesh.AddLine('x',sorted(set(xlines)));mesh.SmoothMeshLines('x',.25,1.4)
ylines=[0]
for c in centres:
    for sign in (-1,1):ylines.extend((c+sign*(w/2-fine/3),c+sign*(w/2+2*fine/3)))
for c in (-.75,.75):
    for edge in (c-.32,c+.32,c-.175,c+.175):ylines.extend((edge-fine/3,edge+2*fine/3))
mesh.AddLine('y',sorted(set(ylines)));mesh.SmoothMeshLines('y',fine,1.4)
mesh.AddLine('y',[-3,3]);mesh.SmoothMeshLines('y',.25,1.4)
mesh.AddLine('z',np.linspace(0,h,a.zdiv+1))
mesh.AddLine('z',[h+t/2,h+t,h+.1,h+.3,2.5]);mesh.SmoothMeshLines('z',.25,1.4)
sub=cs.AddMaterial('FR4_epsilon4p4',epsilon=4.4)
sub.AddBox([-15,-3,0],[15,3,h])
metal=cs.AddMetal('PEC_copper')
for c in centres:metal.AddBox([-15,c-w/2,h],[15,c+w/2,h+t],priority=10)
if a.branch:
    for k,c in enumerate(centres):
        sign=-1 if c<0 else 1
        cy=c+sign*.585
        metal.AddBox([-.127/2,min(c,cy),h],[.127/2,max(c,cy),h+t],priority=10)
        metal.AddBox([-.27,cy-.32,h],[.27,cy+.32,h+t],priority=10)
        metal.AddBox([.75,cy-.32,h],[1.29,cy+.32,h+t],priority=10)
        r=cs.AddLumpedElement('R510_'+str(k),ny='x',caps=True,R=510,LEtype=1)
        r.AddBox([.27,cy-.20,h],[.75,cy+.20,h+t],priority=25)
        metal.AddBox([1.02,cy-.1,h],[1.71,cy+.1,h+t],priority=10)
        metal.AddCylinder([1.71,cy,0],[1.71,cy,h+t],.175,priority=10)
ports=[]
for k,c in enumerate(centres):
    ports += [fd.AddMSLPort(2*k+1,metal,[-15,c-w/2,h],[0,c+w/2,0],'x','z',excite=-1 if k==0 else 1,FeedShift=2,MeasPlaneShift=7,priority=10),
              fd.AddMSLPort(2*k+2,metal,[15,c-w/2,h],[0,c+w/2,0],'x','z',MeasPlaneShift=7,priority=10)]
for port in ports:
    for name in port.I_filenames:
        box=cs.GetPropertiesByName(name)[0].GetPrimitive(0)
        start=box.GetStart();stop=box.GetStop();start[2]=h-fine;stop[2]=h+t+fine
        box.SetStart(start);box.SetStop(stop)
if not a.postprocess:
    assert not(wd/'model.xml').exists(),'Use a fresh work directory'
    cs.Write2XML(str(wd/'model.xml'))
start=time.time()
if not a.postprocess:fd.Run(str(wd),cleanup=True,numThreads=4)
f=np.linspace(50e6,3.3e9,131)
modal=[]
for port in ports:
    port.ReadUIData(str(wd),f);modal.append(port.Z_ref.copy())
    port.CalcPort(str(wd),f,ref_impedance=50)
ad=(ports[0].uf_inc-ports[2].uf_inc)/np.sqrt(2)
s11=(ports[0].uf_ref-ports[2].uf_ref)/np.sqrt(2)/ad
s21=(ports[1].uf_ref-ports[3].uf_ref)/np.sqrt(2)/ad
scd=(ports[1].uf_ref+ports[3].uf_ref)/np.sqrt(2)/ad
back=(ports[1].uf_inc-ports[3].uf_inc)/np.sqrt(2)/ad
band=(f>=.5e9)&(f<=1.5e9)
def pack(z):return dict(real=z.real.tolist(),imag=z.imag.tolist())
out=dict(formal_S_parameters=False,diagnostic_only=True,model=__doc__,branch=a.branch,mesh_mm=fine,zdiv=a.zdiv,elapsed_s=time.time()-start,
         frequencies_Hz=f.tolist(),sdd11=pack(s11),sdd21=pack(s21),scd21=pack(scd),
         modal_Zdiff_ohm=(2*np.mean([z.real for z in modal],axis=0)).tolist(),
         modal_Zdiff_mean_0p5_to1p5GHz=float(2*np.mean([z.real[band] for z in modal])),
         output_backwave_over_incident_max_0p5_to1p5GHz=float(max(abs(back[band]))),
         s21_db_mean_0p5_to1p5GHz=float(np.mean(20*np.log10(abs(s21[band])))))
(wd/'result.json').write_text(json.dumps(out,indent=2)+'\n')
repo=Path(__file__).resolve().parent/'local3d'/wd.name
repo.mkdir(parents=True,exist_ok=True)
shutil.copyfile(wd/'model.xml',repo/'model.xml');shutil.copyfile(wd/'result.json',repo/'result.json')
np.savetxt(repo/'sparameters.csv',np.column_stack((f,s11.real,s11.imag,s21.real,s21.imag,scd.real,scd.imag)),delimiter=',',header='f_Hz,Sdd11_real,Sdd11_imag,Sdd21_real,Sdd21_imag,Scd21_real,Scd21_imag',comments='')
print(json.dumps({k:v for k,v in out.items() if k not in ('frequencies_Hz','sdd11','sdd21','scd21','modal_Zdiff_ohm','model')},indent=1))
