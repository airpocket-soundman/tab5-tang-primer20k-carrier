const p=await eda.dmt_Project.getCurrentProjectInfo();
if(p?.uuid!=="5dcc5c82bf3ef0e5c63ecb708087f825291ce59417579f5268a874044dece84e")throw Error("Wrong project");
const pages=await eda.dmt_Schematic.getAllSchematicPagesInfo();
await eda.dmt_EditorControl.openDocument(pages[0].uuid);
await new Promise(r=>setTimeout(r,3000));
const text=await eda.sch_Netlist.getNetlist("EasyEDA");
if(!text)throw Error("No netlist text");
const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/.claude/worktrees/r5-ovp-switch/spark/usb-jtag-r5-loadsw/easyeda/import-compat/schematic-netlist.json",new Blob([text],{type:"application/json"}),undefined,true);
return {length:text.length,saved};
