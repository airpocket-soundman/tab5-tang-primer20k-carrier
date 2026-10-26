const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/kicad/tab5-fpga-carrier.kicad_sch");
if(!file)throw Error("No schematic file");
const result=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"Existing Project",existingProjectUuid:p.uuid});
return {result,project:await eda.dmt_Project.getCurrentProjectInfo()};
