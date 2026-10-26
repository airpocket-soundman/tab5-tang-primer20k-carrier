const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const sch=p.data.find(x=>x.schematic?.name==="spark-label-power")?.schematic;
if(!sch)throw Error("No corrected schematic");
await eda.dmt_EditorControl.openDocument(sch.page[0].uuid);
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error("No source");
return {schematicUuid:sch.uuid,pageUuid:sch.page[0].uuid,saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/label-main-source.txt",new Blob([source],{type:"text/plain"}),undefined,true)};
