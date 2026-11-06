const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="5dcc5c82bf3ef0e5c63ecb708087f825291ce59417579f5268a874044dece84e")throw Error("Wrong project");
const rules=await eda.pcb_Drc.getCurrentRuleConfiguration();
if(!rules)throw Error("Missing rules");
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
return {applied,basis:"KiCad project minima: copper 0.127mm, hole 0.25mm, board edge 0.3mm, via 0.5mm/drill 0.3mm. All checks retained."};
