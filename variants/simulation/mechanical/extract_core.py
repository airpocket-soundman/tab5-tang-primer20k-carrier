"""Read the official Sipeed Core STEP assembly, preserving part identities.

Requires cadquery-ocp 7.7.2 (geometry kernel only); no invented Core geometry.
"""
from pathlib import Path
import hashlib
import json
import os
import sys

sys.path.insert(0,os.environ.get('CAD_OCP_PYTHON_PATH','D:/tmp/carrier-mechanical/python'))
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence,TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Tool

HERE=Path(__file__).resolve().parent
FILE=Path('D:/tmp/carrier-mechanical/core/STEP/Tang_Primer_20K_3690.step')
doc=TDocStd_Document(TCollection_ExtendedString('core'))
reader=STEPCAFControl_Reader()
reader.SetNameMode(True)
assert int(reader.ReadFile(str(FILE)))==1
assert reader.Transfer(doc)
tool=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
free=TDF_LabelSequence();tool.GetFreeShapes(free)

def name(label):
    attr=TDataStd_Name()
    return str(attr.Get().ToExtString()) if label.FindAttribute(TDataStd_Name.GetID_s(),attr) else ''

rows=[]
def walk(label,depth=0):
    shape=tool.GetShape_s(label)
    bounds=Bnd_Box();BRepBndLib.Add_s(shape,bounds)
    row=dict(name=name(label),depth=depth,bounds_mm=list(bounds.Get()),is_assembly=bool(tool.IsAssembly_s(label)))
    referred=TDF_Label()
    if tool.GetReferredShape_s(label,referred):row['part_type']=name(referred)
    if depth==1 and row['bounds_mm'][3]-row['bounds_mm'][0]>60 and row['bounds_mm'][5]-row['bounds_mm'][2]<1.2:
        exp=TopExp_Explorer(shape,TopAbs_VERTEX);points=set()
        while exp.More():
            p=BRep_Tool.Pnt_s(TopoDS.Vertex_s(exp.Current()))
            points.add(tuple(round(v,5) for v in (p.X(),p.Y(),p.Z())))
            exp.Next()
        row['outline_vertices_mm']=sorted(points)
    rows.append(row)
    components=TDF_LabelSequence()
    if tool.GetComponents_s(label,components,False):
        for i in range(1,components.Length()+1):walk(components.Value(i),depth+1)

for i in range(1,free.Length()+1):walk(free.Value(i))
report=dict(source='Official Sipeed Core_3690_STEP.7z / STEP/Tang_Primer_20K_3690.step',step_sha256=hashlib.sha256(FILE.read_bytes()).hexdigest(),parts=rows)
(HERE/'core_components.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('root shapes',free.Length(),'assembly entries',len(rows))
for row in rows[:14]:print(row)
