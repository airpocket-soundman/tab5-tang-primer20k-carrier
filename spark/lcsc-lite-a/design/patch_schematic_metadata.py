"""Preserve imported source attributes while binding the verified PCB footprints.

SCH component.modify with only otherProperty reset values in EasyEDA3.2.149;
source editing avoids that observed API data loss. No global library is modified.
"""
from pathlib import Path
import sys,json,csv,copy
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'kicad/gen'));import design
def read(p):
 rows=[]
 for line in p.read_text(encoding='utf8').splitlines():
  if '||' in line:
   a,b=line.split('||',1);rows.append([json.loads(a),json.loads(b.rstrip('|'))])
 return rows
pcb=read(H/'easyeda/akizuki-pcb-source.txt');source=read(H/'easyeda/label-main-source.txt')
attrs={}
for h,b in pcb:
 if h['type']=='ATTR':attrs.setdefault(b['parentId'],{})[b['key']]=b['value']
fp={a['Designator']:a['Footprint'] for a in attrs.values() if 'Designator' in a and 'Footprint' in a}
identities={attrs[h['id']]['Designator']:b['attrs']['Unique ID'] for h,b in pcb if h['type']=='COMPONENT'}
sa={}
for h,b in source:
 if h['type']=='ATTR':sa.setdefault(b['parentId'],{})[b['key']]=[h,b]
models={c.ref:c for c in design.build()};bom={ref:r for r in csv.DictReader((H/'kicad/bom.csv').open(encoding='utf8')) for ref in r['Refs'].split(',')}
count=0;ticket=max(h.get('ticket',0) for h,b in source)
for parent,values in sa.items():
 ref=values.get('Designator',[{},{}])[1].get('value')
 if ref not in models:continue
 c=models[ref];lcsc=bom[ref]['LCSC'];updates={'Footprint':fp[ref],'Unique ID':identities[ref],'Value':c.value,'Origin Footprint':c.fp,'LCSC':lcsc,'Supplier':('LCSC' if lcsc else 'Akizuki' if ref in ('J1','J3','JP1','SW3') else ''),'Supplier Part':lcsc,'Comment':c.comment,'Add into BOM':('no' if c.dnp or ref.startswith('H') else 'yes'),'Convert to PCB':'yes'}
 for key,value in updates.items():
  if key in values:values[key][1]['value']=value
  else:
   ticket+=1;template=copy.deepcopy(values['Designator'][1]);template.update(key=key,value=value,keyVisible=False,valueVisible=False)
   source.append([{'type':'ATTR','ticket':ticket,'id':'sparkmeta'+str(ticket)},template])
 count+=1
assert count==118
out='\n'.join(json.dumps(h,separators=(',',':'),ensure_ascii=False)+'||'+json.dumps(b,separators=(',',':'),ensure_ascii=False)+'|' for h,b in source)+'\n'
(H/'easyeda/corrected-schematic-source.txt').write_text(out,encoding='utf8')
print('Preserved and bound metadata:',count)
component_properties={}
for h,b in source:
 if h['type']=='ATTR':component_properties.setdefault(b['parentId'],{})[b['key']]=b['value']
mapping={a['Designator']:a for a in component_properties.values() if a.get('Designator') in models}
code='''const p=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(p?.uuid!=="a4f12572c9bc5e0c68c4d82b95840ad0a1721ae4de88793895acedb594300ee7"||doc?.uuid!=="5ff4950be96b3f65")throw Error("Wrong corrected schematic");
const mapping=MAPPING;
const components=await eda.sch_PrimitiveComponent.getAll();
let count=0;
for(const c of components){
 const ref=c.getState_Designator(),props=mapping[ref];
 if(!props)continue;
 const extra={...props};
 for(const key of ["Device","Symbol","Designator","Name","Unique ID","Add into BOM","Convert to PCB","Manufacturer","Manufacturer Part","Supplier","Supplier Part"])delete extra[key];
 const result=await eda.sch_PrimitiveComponent.modify(c.getState_PrimitiveId(),{designator:ref,name:props.Name,uniqueId:props["Unique ID"],addIntoBom:props["Add into BOM"]==="yes",addIntoPcb:true,manufacturer:props.Manufacturer||"",manufacturerId:props["Manufacturer Part"]||"",supplier:props.Supplier||"",supplierId:props["Supplier Part"]||"",otherProperty:extra});
 if(!result)throw Error("Failed: "+ref);
 count++;
}
return {updated:count};
'''.replace('MAPPING',json.dumps(mapping,ensure_ascii=False))
(H/'easyeda-apply-metadata-api.js').write_text(code,encoding='utf8')
