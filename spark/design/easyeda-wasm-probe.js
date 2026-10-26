const js=await eda.sys_FileSystem.readFileFromFileSystem("D:/tmp/easyeda-ngspice-wasm/ngspice.js");
const wasm=await eda.sys_FileSystem.readFileFromFileSystem("D:/tmp/easyeda-ngspice-wasm/ngspice.wasm");
if(!js||!wasm)throw Error("Official runtime unavailable");
const code=await js.text();
const suffix=`\nself.onmessage=async(event)=>{const logs=[];try{
 const module=await createNgspiceModule({wasmBinary:new Uint8Array(event.data.wasm),noInitialRun:true,print:s=>logs.push(s),printErr:s=>logs.push(s)});
 const engine=new module.NgSpiceWasm();
 engine.loadNetlist("API runtime smoke test\\nV1 in 0 5\\nR1 in out 1k\\nR2 out 0 1k\\n.op\\n.end","");
 const status=engine.run();const raw=engine.getRawResultJson();engine.reset();engine.delete();
 self.postMessage({ok:status===0,status,raw,logs,userAgent:navigator.userAgent,locationProtocol:self.location.protocol});
 }catch(error){self.postMessage({ok:false,error:String(error),logs})}};`;
const url=URL.createObjectURL(new Blob([code,suffix],{type:"application/javascript"}));
let worker;
try{
 worker=new Worker(url);
 const result=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error("WASM smoke test timed out")),20000);
  worker.onmessage=event=>{clearTimeout(timer);resolve(event.data)};
  worker.onerror=event=>{clearTimeout(timer);reject(Error(event.message))};
  wasm.arrayBuffer().then(bytes=>worker.postMessage({wasm:bytes},[bytes]),reject);
 });
 const saved=await eda.sys_FileSystem.saveFileToFileSystem("D:/github/airpocket-soundman/tab5-tang-primer20k-carrier/spark/design/easyeda/wasm-smoke-test.json",new Blob([JSON.stringify(result,null,2)],{type:"application/json"}),undefined,true);
 return {ok:result.ok,status:result.status,error:result.error,saved,rawBytes:result.raw?.length,userAgent:result.userAgent,locationProtocol:result.locationProtocol,logs:result.logs?.slice(-10)};
}finally{worker?.terminate();URL.revokeObjectURL(url)}
