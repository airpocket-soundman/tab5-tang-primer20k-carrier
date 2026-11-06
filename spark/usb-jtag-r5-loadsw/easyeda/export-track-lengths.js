const lines=await eda.pcb_PrimitiveLine.getAll();
const per={};
for(const l of lines){const n=l.getState_Net()||'';const dx=l.getState_EndX()-l.getState_StartX();const dy=l.getState_EndY()-l.getState_StartY();const len=Math.hypot(dx,dy)*0.0254;const key=n+'|'+l.getState_Layer();per[key]=per[key]||{n:0,len:0};per[key].n+=1;per[key].len+=len;}
return {count:lines.length,per};
