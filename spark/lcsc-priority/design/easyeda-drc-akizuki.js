const project=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(project?.uuid!=="1ffa3b3a485f75d1df8d986fa97422aeaf91ad0a1042e90c0f6f2b48301f0162"||doc?.parentProjectUuid!==project.uuid)throw Error("Unexpected PCB context");
const details=await eda.pcb_Drc.check(true,false,true);
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-priority/design/easyeda/akizuki-drc-details.json",new Blob([JSON.stringify(details,null,2)],{type:"application/json"}),undefined,true);
return {projectUuid:project.uuid,detailEntries:details.length,saved};
