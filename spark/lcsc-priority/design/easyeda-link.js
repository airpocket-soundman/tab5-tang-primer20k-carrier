const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="1ffa3b3a485f75d1df8d986fa97422aeaf91ad0a1042e90c0f6f2b48301f0162")throw Error("Wrong project");
const board=await eda.dmt_Board.createBoard("fcdaa9c6b67f9bed","52caa9452ee66dee");
await eda.dmt_EditorControl.openDocument("2d4e35758477c8e0");
const source=await eda.sys_FileManager.getDocumentSource();
if(!source)throw Error("No schematic source");
return {board,saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-priority/design/easyeda/label-main-source.txt",new Blob([source],{type:"text/plain"}),undefined,true)};
