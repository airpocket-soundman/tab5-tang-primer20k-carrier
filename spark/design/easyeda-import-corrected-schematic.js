const uuid="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f";
if(!await eda.dmt_Project.openProject(uuid))throw Error("Cannot open target project");
const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/import-compat/spark-label-power.kicad_sch");
if(!file)throw Error("No corrected schematic");
const result=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"Existing Project",existingProjectUuid:uuid});
return {result};
