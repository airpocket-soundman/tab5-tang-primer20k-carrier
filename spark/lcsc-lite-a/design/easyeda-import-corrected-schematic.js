const uuid="a4f12572c9bc5e0c68c4d82b95840ad0a1721ae4de88793895acedb594300ee7";
if(!await eda.dmt_Project.openProject(uuid))throw Error("Cannot open target project");
const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-lite-a/design/import-compat/spark-label-power.kicad_sch");
if(!file)throw Error("No corrected schematic");
const result=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"Existing Project",existingProjectUuid:uuid});
return {result};
