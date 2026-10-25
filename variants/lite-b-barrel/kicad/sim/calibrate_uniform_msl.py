"""Adapted from the MeOS calibration and the official openEMS MSL tutorial.
Read modal line impedance before any arbitrary 50-ohm normalization.
Straight lossless microstrip calibration, adapted from openEMS MSL_NotchFilter tutorial.
PEC with explicit thickness, er4.4, h0.2104mm; modal MSL ports with measurement planes inside a uniform line.
"""
import os,sys,json,time
from pathlib import Path
import numpy as np
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package',required=True,type=Path)
parser.add_argument('--work-dir',required=True,type=Path)
parser.add_argument('--mesh',type=float,default=.04)
parser.add_argument('--z-divisions',type=int,default=4)
parser.add_argument('--width',type=float,default=.3)
parser.add_argument('--thickness',type=float,default=0)
parser.add_argument('--gap',type=float,default=0)
parser.add_argument('--mode',choices=['odd','even'],default='odd')
parser.add_argument('--postprocess-only',action='store_true')
args=parser.parse_args()
if args.mesh <= 0 or args.z_divisions < 2: parser.error('positive mesh and at least two substrate divisions required')
pkg=str(args.package.resolve())
os.environ['CSXCAD_INSTALL_PATH']=pkg
os.environ['OPENEMS_INSTALL_PATH']=pkg
_dll=os.add_dll_directory(pkg)
from CSXCAD import ContinuousStructure
from openEMS import openEMS
wd=args.work_dir.resolve(); fine=args.mesh
fd=openEMS(NrTS=60000,EndCriteria=1e-5)
fd.SetGaussExcite(5e9,5e9)
fd.SetBoundaryCond(['PML_8','PML_8','MUR','MUR','PEC','MUR'])
cs=ContinuousStructure();fd.SetCSX(cs);mesh=cs.GetGrid();mesh.SetDeltaUnit(1e-3)
h=.2104;w=args.width
mesh.AddLine('x',[-15,-10,-5,0,5,10,15]);mesh.SmoothMeshLines('x',.25,1.4)
centres=[0] if not args.gap else [-(w+args.gap)/2,(w+args.gap)/2]
mesh.AddLine('y',[0]+[c+sgn*(w/2+d) for c in centres for sgn in [-1,1] for d in [-fine/3,2*fine/3]])
mesh.SmoothMeshLines('y',fine,1.4)
mesh.AddLine('y',[-3,3]);mesh.SmoothMeshLines('y',.25,1.4)
mesh.AddLine('z',np.linspace(0,h,args.z_divisions+1));mesh.AddLine('z',[h+.1,h+.3,2.5]);mesh.SmoothMeshLines('z',.25,1.4)
if args.thickness:mesh.AddLine('z',np.linspace(h,h+args.thickness,3))
sub=cs.AddMaterial('substrate',epsilon=4.4);sub.AddBox([-15,-3,0],[15,3,h])
pec=cs.AddMetal('trace')
if args.thickness:
    for c in centres:pec.AddBox([-15,c-w/2,h],[15,c+w/2,h+args.thickness],priority=10)
ports=[]
for k,c in enumerate(centres):
    polarity=-1 if k==0 or args.mode=='even' else 1
    ports.extend([fd.AddMSLPort(2*k+1,pec,[-15,c-w/2,h],[0,c+w/2,0],'x','z',excite=polarity,FeedShift=2,MeasPlaneShift=7,priority=10),fd.AddMSLPort(2*k+2,pec,[15,c-w/2,h],[0,c+w/2,0],'x','z',MeasPlaneShift=7,priority=10)])
if args.thickness:
    for p in ports:
        for name in p.I_filenames:
            box=cs.GetPropertiesByName(name)[0].GetPrimitive(0)
            start=box.GetStart();stop=box.GetStop();start[2]=h-args.mesh;stop[2]=h+args.thickness+args.mesh
            box.SetStart(start);box.SetStop(stop)
wd.mkdir(parents=True,exist_ok=True)
if args.postprocess_only:
    previous=json.loads((wd/'result.json').read_text())
    if previous['lateral_mesh_mm'] != fine or previous.get('substrate_z_divisions',4) != args.z_divisions:
        parser.error('postprocessing parameters must match the saved model')
else:
    if (wd/'model.xml').exists(): parser.error('use a new work directory for each simulation')
    cs.Write2XML(str(wd/'model.xml'))
t=time.time()
if not args.postprocess_only: fd.Run(str(wd),cleanup=True,numThreads=4)
f=np.linspace(.5e9,2e9,61)
modal=[]
for p in ports:
    p.ReadUIData(str(wd),f)
    modal.append(p.Z_ref.copy())
    p.CalcPort(str(wd),f,ref_impedance=50)
a=ports[0].uf_ref/ports[0].uf_inc;b=ports[1].uf_ref/ports[0].uf_inc
z=50*np.sqrt(((1+a)**2-b*b)/((1-a)**2-b*b))
out={'model':'straight lossless PEC microstrip with explicit thickness parameter, modal MSL ports','width_mm':w,'gap_mm':args.gap,'thickness_mm':args.thickness,'mode':args.mode,'h_mm':h,'er':4.4,'lateral_mesh_mm':fine,'substrate_z_divisions':args.z_divisions,'postprocess_only':args.postprocess_only,'elapsed_this_invocation_s':time.time()-t,'z_mean_ohm':float(np.mean([a.real.mean() for a in modal])), 'modal_port1_ohm':modal[0].real.tolist(), 'modal_port2_ohm':modal[1].real.tolist(), 'old_apparent_z_mean_ohm':float(z.real.mean()), 'output_incident_over_input_incident_max':float(np.max(abs(ports[1].uf_inc/ports[0].uf_inc))),'z_min_ohm':float(min(a.real.min() for a in modal)),'z_max_ohm':float(max(a.real.max() for a in modal)),'s21_db_mean':float(np.mean(20*np.log10(abs(b)))),'frequencies_hz':f.tolist(),'z_real_ohm':np.mean([a.real for a in modal],axis=0).tolist(), 'modal_all_ports_ohm':[a.real.tolist() for a in modal], 'zdiff_ohm':float(2*np.mean([a.real.mean() for a in modal])) if args.gap and args.mode=='odd' else None}
(wd/'result.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if not isinstance(v,list)}))
