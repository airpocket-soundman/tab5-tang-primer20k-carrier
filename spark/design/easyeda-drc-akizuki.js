const project=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(project?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f"||doc?.parentProjectUuid!==project.uuid)throw Error("Unexpected PCB context");
const details=await eda.pcb_Drc.check(true,false,true);
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/akizuki-drc-details.json",new Blob([JSON.stringify(details,null,2)],{type:"application/json"}),undefined,true);
return {projectUuid:project.uuid,detailEntries:details.length,saved};
