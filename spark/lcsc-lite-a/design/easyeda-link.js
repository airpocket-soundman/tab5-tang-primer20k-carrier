const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="a4f12572c9bc5e0c68c4d82b95840ad0a1721ae4de88793895acedb594300ee7")throw Error("Wrong project");
const board=await eda.dmt_Board.createBoard("7798b889c65e5ea5","52caa9452ee66dee");
await eda.dmt_EditorControl.openDocument("5ff4950be96b3f65");
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error("No schematic source");
return {board,saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-lite-a/design/easyeda/label-main-source.txt",new Blob([source],{type:"text/plain"}),undefined,true)};
