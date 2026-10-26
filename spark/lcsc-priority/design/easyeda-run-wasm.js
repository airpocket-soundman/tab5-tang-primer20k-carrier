const base="D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/lcsc-priority/simulation/easyeda-wasm/";
const runtime="D:/tmp/easyeda-ngspice-wasm/";
async function read(path){const f=await eda.sys_FileSystem.readFileFromFileSystem(path);if(!f)throw Error("Missing file: "+path);return f}
const [loader,models,workerFile,wasmFile,inputFile]=await Promise.all([read(runtime+"ngspice.js"),read(runtime+"ngspice-xspice-codemodels.js"),read(base+"worker.js"),read(runtime+"ngspice.wasm"),read(base+"active-input.json")]);
const input=JSON.parse(await inputFile.text());
const wasm=await wasmFile.arrayBuffer();
const url=URL.createObjectURL(new Blob([await loader.text(),"\n",await models.text(),"\n",await workerFile.text()],{type:"application/javascript"}));
const summaries=[];
try{
 for(const c of input.cases){
  const worker=new Worker(url);
  try{
   const result=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error("Case timed out: "+c.name)),c.analysis?.kind==="periodic"?27500:22000);
    worker.onmessage=e=>{clearTimeout(timer);resolve(e.data)};
    worker.onerror=e=>{clearTimeout(timer);reject(Error(e.message))};
    worker.postMessage({wasm,netlist:c.netlist,compatMode:c.compatMode||"",analysis:c.analysis});
   });
   const diagnostics=result.raw?JSON.parse(result.raw).diagnostics:undefined;
   if(c.analysis&&result.raw){
    result.rawPath="D:/tmp/easyeda-ngspice-wasm/raw-lcsc/"+c.name+".json";
    const rawSaved=await eda.sys_FileSystem.saveFileToFileSystem(result.rawPath,new Blob([result.raw],{type:"application/json"}),undefined,true);
    if(!rawSaved)throw Error("Raw result not saved");
    delete result.raw;
   }
   const saved=await eda.sys_FileSystem.saveFileToFileSystem(base+"results/"+c.name+".json",new Blob([JSON.stringify({...result,diagnostics,caseName:c.name,source:c.source},null,2)],{type:"application/json"}),undefined,true);
   summaries.push({caseName:c.name,ok:result.ok,status:result.status,error:result.error,runtimeMs:result.runtimeMs,saved,engine:result.engine,diagnostics});
   if(!result.ok)break;
  }finally{worker.terminate()}
 }
 return {cases:summaries,executedInside:"EasyEDA API Gateway browser Worker",allPassed:summaries.length===input.cases.length&&summaries.every(c=>c.ok&&c.saved)};
}finally{URL.revokeObjectURL(url)}
