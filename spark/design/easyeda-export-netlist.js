const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const file=await eda.sch_ManufactureData.getNetlistFile("spark-migration-netlist","EasyEDA");
if(!file)throw Error("No netlist file");
return {name:file.name,saved:await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/schematic-netlist.txt",file,undefined,true)};
