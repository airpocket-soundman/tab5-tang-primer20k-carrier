const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="a4f12572c9bc5e0c68c4d82b95840ad0a1721ae4de88793895acedb594300ee7")throw Error("Wrong project");
await eda.dmt_EditorControl.openDocument("5ff4950be96b3f65");
const file=await eda.sch_ManufactureData.getNetlistFile("spark-migration-netlist","EasyEDA");
if(!file)throw Error("No netlist file");
return {name:file.name,saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-lite-a/design/easyeda/schematic-netlist.txt",file,undefined,true)};
