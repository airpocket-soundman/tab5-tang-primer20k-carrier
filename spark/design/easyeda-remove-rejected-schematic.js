const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const bad=p.data.find(x=>x.schematic?.uuid==="d563695cbb810aba");
const good=p.data.find(x=>x.schematic?.uuid==="0c2263c862d746ed"&&x.pcb?.uuid==="52caa9452ee66dee");
if(!good||!bad||bad.pcb)throw Error("Unsafe intermediate cleanup context");
// Only our rejected import, whose raw source/netlist are already saved locally.
return {removedRejectedSchematic:await eda.dmt_Schematic.deleteSchematic(bad.schematic.uuid)};
