const comps=await eda.pcb_PrimitiveComponent.getAll();
const idToRef={};
for(const c of comps){idToRef[c.getState_PrimitiveId()]=c.getState_Designator();}
const pads=await eda.pcb_PrimitivePad.getAll();
const out=[];
for(const p of pads){const par=p.getState_ParentComponentPrimitiveId?p.getState_ParentComponentPrimitiveId():null;out.push([idToRef[par]||null,String(p.getState_PadNumber()),p.getState_Net()||'',Math.round(p.getState_X()*0.0254*1000)/1000,Math.round(p.getState_Y()*0.0254*1000)/1000]);}
const nets=await eda.pcb_Net.getAllNetsName();
return {n:out.length,pads:out,nets};
