const uuid="1ffa3b3a485f75d1df8d986fa97422aeaf91ad0a1042e90c0f6f2b48301f0162";
if(!await eda.dmt_Project.openProject(uuid))throw Error("Cannot open target project");
const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-priority/design/import-compat/spark-label-power.kicad_sch");
if(!file)throw Error("No corrected schematic");
const result=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"Existing Project",existingProjectUuid:uuid});
return {result};
