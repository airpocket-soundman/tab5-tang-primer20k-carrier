const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/import-compat/spark-label-power.kicad_sch");
if(!file)throw Error("No compatibility schematic");
const project=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"New Project",newProjectOwnerTeamUuid:"C:\\Users\\yamashita_y00031\\Documents\\EasyEDA-Pro\\projects",newProjectName:"spark-power-label-migration-temp-20261026",newProjectFriendlyName:"Spark Power Label Migration Temporary",newProjectDescription:"Intermediate conversion only; not a released design"});
if(!project)throw Error("No project");
return {project,opened:await eda.dmt_Project.openProject(project.uuid)};
