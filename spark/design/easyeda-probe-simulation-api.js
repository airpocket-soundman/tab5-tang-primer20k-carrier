// Read-only capability probe. Never inject fabricated simulation result events.
const project=await eda.dmt_Project.getCurrentProjectInfo();
if(project?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Unexpected project");
await eda.dmt_EditorControl.openDocument("f11178e72fa334b0");
const document=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(document?.parentProjectUuid!==project.uuid)throw Error("Wrong document context");
let listener;
try{
 eda.sch_Event.addSimulationEnginePullEventListener("spark-simulation-capability-probe","all",()=>{});
 listener={registrationSucceeded:true,removed:eda.sch_Event.removeEventListener("spark-simulation-capability-probe")};
}catch(error){listener={registrationSucceeded:false,error:String(error)}}
let file;
try{
 const exported=await eda.sch_ManufactureData.getSimulationNetlistFile("spark-simulation-capability-probe","NGspice");
 file=exported?{available:true,name:exported.name,bytes:exported.size}:{available:false};
}catch(error){file={available:false,error:String(error)}}
const shortcuts=await eda.sys_ShortcutKey.getShortcutKeys(true);
return {projectUuid:project.uuid,document,simulationApi:{pushData:typeof eda.sch_SimulationEngine.pushData,exportNetlist:typeof eda.sch_ManufactureData.getSimulationNetlistFile,listener},simulationNetlist:file,simulationShortcuts:shortcuts.filter(s=>/simulat|ngspice|仿真/i.test(s.title)),scope:"Capability probe only; no simulation was executed and no design objects modified"};
