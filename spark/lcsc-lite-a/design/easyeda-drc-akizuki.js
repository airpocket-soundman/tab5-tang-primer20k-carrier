const project=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(project?.uuid!=="a4f12572c9bc5e0c68c4d82b95840ad0a1721ae4de88793895acedb594300ee7"||doc?.parentProjectUuid!==project.uuid)throw Error("Unexpected PCB context");
const details=await eda.pcb_Drc.check(true,false,true);
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-lite-a/design/easyeda/akizuki-drc-details.json",new Blob([JSON.stringify(details,null,2)],{type:"application/json"}),undefined,true);
return {projectUuid:project.uuid,detailEntries:details.length,saved};
