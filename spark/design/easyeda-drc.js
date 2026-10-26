const project=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(project?.uuid!=="8b55c295039849eff0b8170876b8b9828d103c48dd3ea0b78772b2c9bdc34a9b"||doc?.parentProjectUuid!==project.uuid||doc?.documentType!==3)throw Error("Expected final review PCB");
const details=await eda.pcb_Drc.check(true,false,true);
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/drc-details.json",new Blob([JSON.stringify(details,null,2)],{type:"application/json"}),undefined,false);
return {projectUuid:project.uuid,detailEntries:details.length,saved,detailsType:typeof details[0]};
