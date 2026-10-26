const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="2a831d7f46f9f57bdfa50d58fdf428af1d6887005fcb09d4675d9b975fc7c130")throw Error("Wrong temporary project");
const sch=p.data.find(x=>x.itemType==="Board"&&x.schematic)?.schematic;
if(!sch)throw Error("No schematic");
await eda.dmt_EditorControl.openDocument(sch.page[0].uuid);
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error("No source");
return {saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/label-schematic-source.txt",new Blob([source],{type:"text/plain"}),undefined,true)};
