/* Run the unmodified official NGspice WASM inside an EasyEDA extension Worker.
   This adapter only sets up virtual files and captures genuine engine output. */
self.onmessage=async(event)=>{
 const logs=[];const started=performance.now();
 try{
  const module=await createNgspiceModule({wasmBinary:new Uint8Array(event.data.wasm),noInitialRun:true,print:s=>logs.push(s),printErr:s=>logs.push(s)});
  const codeModels=globalThis.__JLC_NGSPICE_XSPICE_CODEMODELS;
  if(!codeModels)throw Error("Missing official XSPICE code models");
  const names=Object.keys(codeModels);
  for(const dir of ["/usr/lib/ngspice","/mingw64/lib/ngspice","/usr/share/ngspice/scripts"]){module.FS.mkdirTree(dir)}
  for(const name of names){
   const value=codeModels[name];const binary=atob(Array.isArray(value)?value.join(""):value);const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
   module.FS.writeFile("/usr/lib/ngspice/"+name,bytes);
   module.FS.writeFile("/mingw64/lib/ngspice/"+name,bytes);
   module.loadDynamicLibrary("/mingw64/lib/ngspice/"+name,{global:true,nodelete:true,allowUndefined:true});
  }
  module.FS.writeFile("/usr/share/ngspice/scripts/spinit","set xspice_enabled\n"+names.map(n=>"codemodel /mingw64/lib/ngspice/"+n).join("\n")+"\n");
  const engine=new module.NgSpiceWasm();
  engine.loadNetlist(event.data.netlist,event.data.compatMode||"");
  const status=engine.run();
  let exportSampling="adaptive solver output";
  if(event.data.analysis?.kind==="periodic"&&status===0){
   // Preserve solver equations/timesteps. Only resample the completed result
   // onto the existing .tran output interval to stay below the wrapper cap.
   if(engine.command("linearize v("+event.data.analysis.receiver+")")!==0)throw Error("Periodic result linearize failed");
   if(engine.command("destroy tran1")!==0)throw Error("Original adaptive plot cleanup failed");
   exportSampling="Post-solve ngspice linearize at existing .tran tstep100ps; original adaptive plot exceeds100000-point export cap";
  }
  const raw=engine.getRawResultJson();
  engine.reset();engine.delete();
  const parsed=JSON.parse(raw);const errors=parsed.diagnostics?.errors||[];
  let summary;
  if(event.data.analysis?.kind==="periodic"&&status===0&&errors.length===0){
   const a=event.data.analysis;const plot=parsed.plots.find(p=>p.name.startsWith("tran"));
   if(!plot)throw Error("No periodic transient plot");
   const vectors=Object.fromEntries(plot.vectors.map(v=>[v.name.toLowerCase(),v.real]));const time=vectors.time;const recv=vectors[a.receiver.toLowerCase()];
   if(time[time.length-1]<(3*a.period+10e-9)*.999)throw Error("Incomplete periodic transient");
   function interp(x){let lo=0,hi=time.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(time[mid]<=x)lo=mid;else hi=mid}return recv[lo]+(recv[hi]-recv[lo])*(x-time[lo])/(time[hi]-time[lo])}
   const highs=[0,1,2].map(i=>interp(10e-9+(i+.25)*a.period));const lows=[0,1,2].map(i=>interp(10e-9+(i+.75)*a.period));
   summary={freq_Hz:a.freq_Hz,corner:a.corner,direction:a.direction,samples:time.length,sample_high_min_V:Math.min(...highs),sample_low_max_V:Math.max(...lows),threshold_ok:Math.min(...highs)>=a.thresholds[0]&&Math.max(...lows)<=a.thresholds[1]};
  }else if(event.data.analysis?.kind==="hdmi"&&status===0&&errors.length===0){
   const a=event.data.analysis,plot=parsed.plots.find(p=>p.name.startsWith("tran"));
   if(!plot)throw Error("No HDMI transient plot");
   const vv=Object.fromEntries(plot.vectors.map(v=>[v.name.toLowerCase(),v.real]));
   if(vv.time[vv.time.length-1]<129*a.bit_period_s*.9999)throw Error("Incomplete HDMI transient");
   summary={kind:"hdmi",lane:a.lane,rate_bps:a.rate_bps,corner:a.corner,samples:vv.time.length,scope:a.scope};
  }else if(event.data.analysis&&status===0&&errors.length===0){
   const a=event.data.analysis;const plot=parsed.plots.find(p=>p.name.startsWith("tran"));
   if(!plot)throw Error("No transient plot");
   const vectors=Object.fromEntries(plot.vectors.map(v=>[v.name.toLowerCase(),v.real]));const time=vectors.time;
   if(time[time.length-1]<219e-9)throw Error("Incomplete communication transient");
   const extrema={};
   for(const [name,node] of Object.entries(a.saved)){
    const values=vectors[node.toLowerCase()];if(!values)throw Error("Missing vector "+node);
    let high=-Infinity,low=Infinity;for(const v of values){high=Math.max(high,v);low=Math.min(low,v)}
    extrema[name]={max:high,min_rising:low,min_falling_by_linearity:Math.min(0,a.vdd-high)};
   }
   const recv=vectors[a.saved.GPIO_receiver.toLowerCase()];let lastBad=-1;
   for(let i=0;i<time.length;i++)if(time[i]>=10e-9&&Math.abs(recv[i]-a.vdd)>.05*a.vdd)lastBad=i;
   if(Math.abs(recv[recv.length-1]-a.vdd)>.05*a.vdd)throw Error("Receiver not settled");
   const safe=(e,hi,lo)=>e.max<=hi&&e.min_falling_by_linearity>=lo;
   summary={signal:a.signal,corner:a.corner,direction:a.direction,samples:time.length,pin_extrema_V:extrema,settle_5percent_ns:lastBad<0?0:(time[lastBad]-10e-9)*1e9,receiver_voltage_ok:safe(extrema.GPIO_receiver,3.6,-.3),source_voltage_ok:safe(extrema.GPIO_driver_pad,3.6,-.3),switch_design_envelope_ok:safe(extrema.switch_host_pin,5.5,-.5)&&safe(extrema.switch_core_pin,5.5,-.5)};
  }
  self.postMessage({ok:status===0&&errors.length===0,status,raw,summary,exportSampling,logs,runtimeMs:performance.now()-started,userAgent:navigator.userAgent,engine:"Official EasyEDA NGspice46 WASM; executed in EasyEDA API Gateway Worker"});
 }catch(error){self.postMessage({ok:false,error:String(error),logs,runtimeMs:performance.now()-started})}
};
