const p=await eda.dmt_Project.getCurrentProjectInfo();
const pcbs=await eda.dmt_Pcb.getAllPcbsInfo();
const schs=await eda.dmt_Schematic.getAllSchematicsInfo();
const pages=await eda.dmt_Schematic.getAllSchematicPagesInfo();
const boards=await eda.dmt_Board.getAllBoardsInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
return {project:p&&{uuid:p.uuid,name:p.friendlyName},pcbs,schs,pages:(pages||[]).map(x=>({uuid:x.uuid,name:x.name,parent:x.parentSchematicUuid})),boards,doc};
