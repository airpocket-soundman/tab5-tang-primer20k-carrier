const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/.claude/worktrees/r5-ovp-switch/spark/usb-jtag-r5-loadsw/easyeda/import-compat/r5l-kicad-compat-import.zip");
if(!file)throw Error("Compatibility archive is not readable");
const project=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"New Project",newProjectOwnerTeamUuid:"C:\\Users\\yamashita_y00031\\Documents\\EasyEDA-Pro\\projects",newProjectName:"tab5-spark-r5l-loadsw-20261106",newProjectFriendlyName:"Tab5 Spark r5l load switch",newProjectDescription:"KiCad-derived import of r5l (SW4 signal-only + P-MOS load switches). Importer compatibility copy with numbered nets; the KiCad source is authoritative. Not hardware verified."});
if(!project)throw Error("Import returned no project");
const opened=await eda.dmt_Project.openProject(project.uuid);
return {project,opened,boards:await eda.dmt_Board.getAllBoardsInfo()};
