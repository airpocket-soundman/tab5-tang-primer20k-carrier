const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const sch=p.data.find(x=>x.itemType==="Board"&&x.schematic)?.schematic;
const pcb=p.data.find(x=>x.itemType==="PCB");
if(!sch||!pcb)throw Error("Missing schematic/PCB");
return {board:await eda.dmt_Board.createBoard(sch.uuid,pcb.uuid),schematicUuid:sch.uuid,pcbUuid:pcb.uuid};
