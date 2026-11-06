const pages=await eda.dmt_Schematic.getAllSchematicPagesInfo();
await eda.dmt_EditorControl.openDocument(pages[0].uuid);
await new Promise(r=>setTimeout(r,4000));
const comps=await eda.sch_PrimitiveComponent.getAll();
const out=[];
for(const c of comps){out.push([c.getState_Designator?c.getState_Designator():null,c.getState_Name?c.getState_Name():null,c.getState_Net?c.getState_Net():null]);}
const wires=eda.sch_PrimitiveWire?await eda.sch_PrimitiveWire.getAll():[];
return {pages:pages.length,components:comps.length,wires:wires.length,designators:out.filter(x=>x[0]).map(x=>x[0]).sort(),noDesignator:out.filter(x=>!x[0]).length};
