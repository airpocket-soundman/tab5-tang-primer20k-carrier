const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f")throw Error("Wrong project");
const rules=await eda.pcb_Drc.getCurrentRuleConfiguration();
if(!rules)throw Error("Missing rules");
// Reproduce the actual reviewed KiCad project minima, not zero/disabled checks.
const matrix=rules.config.Spacing["Safe Spacing"].copperThickness1oz;
if(matrix.unit!=="mm")throw Error("Unexpected rule units");
const copper=new Set(["Track","SMD Pad","TH Pad","SMD Test Point","TH Test Point","Via","Fill Region/Teardrop","Copper/Plane Zone"]);
const table=matrix.tables["1"].content;
for(let r=0;r<table.length;r++)for(let c=0;c<table[r].length;c++){
 const row=matrix.row[r],col=matrix.column[c];
 if(copper.has(row)&&copper.has(col))table[r][c]=0.127;
 if(row==="Hole"&&copper.has(col))table[r][c]=0.25;
 if((row==="Board Outline"&&copper.has(col))||(copper.has(row)&&col==="Board Outline"))table[r][c]=0.3;
}
rules.config.Spacing["Other Spacing"].otherClearance.form.hole2Hole=0.25;
const via=rules.config.Physics["Via Size"].viaSize.form;
via.viaOuterdiameterMin=0.5;via.viaInnerdiameterMin=0.3;
via.viaOuterdiameterDefault=0.6;via.viaInnerdiameterDefault=0.3;
const applied=await eda.pcb_Drc.overwriteCurrentRuleConfiguration(rules.config);
if(!applied)throw Error("Rules not applied");
const reread=await eda.pcb_Drc.getCurrentRuleConfiguration();
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/akizuki-rules-aligned.json",new Blob([JSON.stringify(reread,null,2)],{type:"application/json"}),undefined,true);
return {applied,saved,basis:"KiCad project copper0.127mm, hole0.25mm, edge0.3mm, via0.5mm/drill0.3mm; all checks retained. Fabricator DFM approval still required."};
