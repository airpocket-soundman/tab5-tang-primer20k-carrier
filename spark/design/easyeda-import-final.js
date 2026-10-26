const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/spark-kicad-engineering-import.zip");
if(!file)throw Error("Input archive is not readable");
const project=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"New Project",newProjectOwnerTeamUuid:"C:\\Users\\yamashita_y00031\\Documents\\EasyEDA-Pro\\projects",newProjectName:"tab5-spark-full-pcba-review-20261026",newProjectFriendlyName:"Tab5 Spark Full PCBA Review",newProjectDescription:"Engineering review imported from checked KiCad source. Not certified eligible for Spark;100% EasyEDA design requirement and import eligibility require organizer confirmation."});
if(!project)throw Error("Import did not return a project");
const opened=await eda.dmt_Project.openProject(project.uuid);
return {project,opened,boards:await eda.dmt_Board.getAllBoardsInfo()};
