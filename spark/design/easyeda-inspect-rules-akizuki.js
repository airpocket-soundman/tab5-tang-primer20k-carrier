const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const rules=await eda.pcb_Drc.getCurrentRuleConfiguration();
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/akizuki-rules-before.json",new Blob([JSON.stringify(rules,null,2)],{type:"application/json"}),undefined,true);
return {saved};
