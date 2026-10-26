const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="1ffa3b3a485f75d1df8d986fa97422aeaf91ad0a1042e90c0f6f2b48301f0162")throw Error("Wrong project");
await eda.dmt_EditorControl.openDocument("2d4e35758477c8e0");
const file=await eda.sch_ManufactureData.getNetlistFile("spark-migration-netlist","EasyEDA");
if(!file)throw Error("No netlist file");
return {name:file.name,saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-priority/design/easyeda/schematic-netlist.txt",file,undefined,true)};
