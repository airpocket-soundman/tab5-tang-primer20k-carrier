const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/spark-kicad-compat-import.zip");
if(!file)throw Error("Compatibility archive is not readable");
const project=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"New Project",newProjectOwnerTeamUuid:"C:\\Users\\yamashita_y00031\\Documents\\EasyEDA-Pro\\projects",newProjectName:"tab5-spark-compat-review-20261026",newProjectFriendlyName:"Tab5 Spark Compatibility Review",newProjectDescription:"KiCad-derived compatibility review with explicitly numbered nets. Not an eligible100% EasyEDA design claim. Recheck all copper, nets, rules, and footprint mapping."});
if(!project)throw Error("Import returned no project");
return {project,opened:await eda.dmt_Project.openProject(project.uuid)};
