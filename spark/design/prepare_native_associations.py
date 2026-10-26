from pathlib import Path
import json
H=Path(__file__).resolve().parent
rows=[]
for l in (H/'easyeda/akizuki-pcb-source.txt').read_text(encoding='utf8').splitlines():
 if '||' in l:
  h,b=l.split('||',1);rows.append((json.loads(h),json.loads(b.rstrip('|'))))
attrs={}
for h,b in rows:
 if h['type']=='ATTR':attrs.setdefault(b['parentId'],{})[b['key']]=b['value']
mapping={a['Designator']:a['Footprint'] for a in attrs.values() if 'Designator' in a and 'Footprint' in a}
identities={attrs[h['id']]['Designator']:b['attrs']['Unique ID'] for h,b in rows if h['type']=='COMPONENT'}
(H/'easyeda/footprint-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
code='''const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const components=await eda.sch_PrimitiveComponent.getAll();
const c=components.find(c=>c.getState_Designator()==="J1");
if(!c)throw Error("J1 absent");
const before=c.getState_Footprint();
const updated=await eda.sch_PrimitiveComponent.modify(c.getState_PrimitiveId(),{otherProperty:{Footprint:FP}});
return {before,after:updated?.getState_Footprint()};
'''.replace('FP',json.dumps(mapping['J1']))
(H/'easyeda-test-association.js').write_text(code)
code='''const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const mapping=MAPPING, identities=IDENTITIES;
const components=await eda.sch_PrimitiveComponent.getAll();
const done=[];
for(const c of components){
 const ref=c.getState_Designator();
 if(!mapping[ref])continue;
 const updated=await eda.sch_PrimitiveComponent.modify(c.getState_PrimitiveId(),{uniqueId:identities[ref],otherProperty:{Footprint:mapping[ref]}});
 if(updated?.getState_Footprint()?.uuid!==mapping[ref])throw Error("Footprint association failed: "+ref);
 done.push(ref);
}
if(done.length!==Object.keys(mapping).length)throw Error("Component reference count mismatch");
return {associated:done.length,pcbUniqueIdsMatched:true,refs:done};
'''.replace('MAPPING',json.dumps(mapping)).replace('IDENTITIES',json.dumps(identities))
(H/'easyeda-associate-footprints.js').write_text(code)
