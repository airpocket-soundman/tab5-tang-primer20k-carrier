const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const components=await eda.sch_PrimitiveComponent.getAll();
const c=components.find(c=>c.getState_Designator()==="J1");
if(!c)throw Error("J1 absent");
const before=c.getState_Footprint();
const updated=await eda.sch_PrimitiveComponent.modify(c.getState_PrimitiveId(),{otherProperty:{Footprint:"60f63300c7161e95"}});
return {before,after:updated?.getState_Footprint()};
