const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-lite-a/design/import-compat/tab5-fpga-carrier.kicad_pcb");
if(!file)throw Error("Compatibility PCB not readable");
const project=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"New Project",newProjectOwnerTeamUuid:"C:\\Users\\yamashita_y00031\\Documents\\EasyEDA-Pro\\projects",newProjectName:"tab5-spark-lite-a-lcsc-20261026",newProjectFriendlyName:"Tab5 Spark Lite A LCSC Priority",newProjectDescription:"Lite A99x78 HDMI and USB PD; LCSC priority PCBA and equivalent-circuit validation, eligibility unconfirmed; not fabrication release."});
if(!project)throw Error("PCB import returned no project");
return {project,opened:await eda.dmt_Project.openProject(project.uuid)};
