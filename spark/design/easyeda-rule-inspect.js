const rule=await eda.pcb_Drc.getCurrentRuleConfiguration();
const vias=await eda.pcb_PrimitiveVia.getAll();
const nearby=vias.map(v=>({id:v.getState_PrimitiveId(),x:v.getState_X(),y:v.getState_Y(),net:v.getState_Net()})).sort((a,b)=>(Math.abs(a.x-397.637795)+Math.abs(a.y+1165.354331))-(Math.abs(b.x-397.637795)+Math.abs(b.y+1165.354331))).slice(0,3);
return {rule,nearby};
