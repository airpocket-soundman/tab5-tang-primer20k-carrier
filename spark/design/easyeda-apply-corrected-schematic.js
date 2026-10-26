const p=await eda.dmt_Project.getCurrentProjectInfo();
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(p?.uuid!=="b7a6783339159b0708ab3bf639c202306b62d83ae5fc2c3bf655e9d774467d8f"||doc?.uuid!=="f11178e72fa334b0")throw Error("Wrong corrected schematic");
const file=await eda.sys_FileSystem.readFileFromFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/corrected-schematic-source.txt");
if(!file)throw Error("No corrected source");
const applied=await eda.sys_FileManager.setDocumentSource(await file.text());
if(!applied)throw Error("Source not applied");
return {applied};
