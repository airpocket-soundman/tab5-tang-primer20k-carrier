const pages=await eda.dmt_Schematic.getAllSchematicPagesInfo();
const page=pages.find(x=>x.parentSchematicUuid==="1807cda4dd01f352");
if(!page)throw Error("Label schematic page not found");
await eda.dmt_EditorControl.openDocument(page.uuid);
await new Promise(r=>setTimeout(r,4000));
const comps=await eda.sch_PrimitiveComponent.getAll();
const des=comps.map(c=>c.getState_Designator()).filter(Boolean);
await eda.sys_Log.clear?.();
const details=await eda.sch_Drc.check(true,false,true);
const lines=await eda.sys_Log.sort();
const text=lines.map(l=>(l.message||l.text||JSON.stringify(l)));
const start=text.map((t,i)=>/Start Design Rule Checking/.test(t)?i:-1).filter(i=>i>=0).pop()||0;
const recent=text.slice(start);
const kinds={};
for(const t of recent){const k=t.replace(/\b[A-Z]+\d+(\(\$\w+\))?/g,"X").replace(/\$\w+/g,"$").replace(/\d+/g,"#").slice(0,110);kinds[k]=(kinds[k]||0)+1;}
const sorted=Object.entries(kinds).sort((a,b)=>b[1]-a[1]).slice(0,14);
return {components:comps.length,real:des.filter(d=>!d.startsWith('#')).length,drc:details,logLines:recent.length,kinds:sorted,sample:recent.slice(0,6).map(t=>t.slice(0,200))};
