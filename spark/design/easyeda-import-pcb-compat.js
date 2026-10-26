const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/import-compat/tab5-fpga-carrier.kicad_pcb");
if(!file)throw Error("Compatibility PCB not readable");
const project=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",undefined,{operation:"New Project",newProjectOwnerTeamUuid:"C:\\Users\\yamashita_y00031\\Documents\\EasyEDA-Pro\\projects",newProjectName:"tab5-spark-pcb-compat-20261026",newProjectFriendlyName:"Tab5 Spark PCB Compatibility Review",newProjectDescription:"Post-simulation engineering migration; KiCad-derived. Electrical migration must pass independent comparison. Spark eligibility remains unconfirmed."});
if(!project)throw Error("Single PCB import returned no project");
return {project,opened:await eda.dmt_Project.openProject(project.uuid)};
