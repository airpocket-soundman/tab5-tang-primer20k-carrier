
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg reset_n=0,abort=0,clear=0,memory_ready=1,job_valid=0,out_ready=0;
reg[31:0] job_m,job_k,job_n,job_a_base,job_a_pitch,job_b_base,job_b_pitch,job_c_base,job_c_pitch;
wire job_ready,busy,out_valid,result_valid,error,quarantined;wire[3:0] error_code;
wire[31:0] accepted_tiles,completed_tiles,expected_tiles;
wire descriptor_valid;reg descriptor_ready=0;
wire[4:0] cfg_ic,cfg_oh,cfg_ow;wire[3:0] cfg_oc;wire[1:0] cfg_kernel,cfg_stride;
wire first_block,final_block;wire[15:0] input_full_h,input_full_w;
wire signed[31:0] input_origin_y,input_origin_x;
wire[31:0] input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch;
wire output_tail_owned;reg tile_busy=0,tile_done=0,tile_error=0,tile_quarantined=0,tile_result_valid=0;wire tile_abort;
npu_ddr_matmul_sequencer #(.TILE_TIMEOUT(80),.DRAIN_TIMEOUT(12))dut(.*);
integer mode=0,cycle_count=0,timer=0,sticky=0,seen=0;reg saved_final=0;
always @(negedge clk)begin
 cycle_count=cycle_count+1;
 descriptor_ready=mode!=6&&(cycle_count%5!=0)&&(cycle_count%7!=0);
 if(!reset_n)begin tile_busy=0;tile_done=0;tile_error=0;tile_quarantined=0;tile_result_valid=0;timer=0;sticky=0;seen=0;end
 else if(tile_abort&&mode!=3)begin
  tile_busy=0;timer=0;
  if(sticky>0)begin sticky=sticky-1;if(sticky==0)tile_done=0;end
 end else if(tile_busy)begin
  if(mode!=3)begin
   timer=timer-1;
   if(timer==0)begin tile_busy=0;tile_done=1;sticky=3;tile_result_valid=saved_final&&mode!=5;
    if(mode==1)tile_error=1;if(mode==2)tile_quarantined=1;
   end
  end
 end else if(tile_done)begin sticky=sticky-1;if(sticky==0)tile_done=0;end
end
integer observed;
reg stalled=0;reg[511:0] saved_descriptor;
wire[511:0] descriptor_bundle={cfg_ic,cfg_oc,cfg_oh,cfg_ow,cfg_kernel,cfg_stride,first_block,final_block,input_full_h,input_full_w,input_origin_y,input_origin_x,input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch,output_tail_owned};
always @(posedge clk)begin
 if(!reset_n)stalled<=0;
 else begin
  if(descriptor_valid&&!descriptor_ready)begin
   if(stalled&&descriptor_bundle!==saved_descriptor)$fatal(1,"descriptor changed under backpressure");
   saved_descriptor<=descriptor_bundle;stalled<=1;
  end else stalled<=0;
 end
end
integer f,scan,jid,nexp,expected_error,jobs=0,total=0,idx,i,t;reg[31:0] ex[0:18];
reg checking=0;reg[31:0] hold_count;
always @(posedge clk)begin
 if(reset_n&&descriptor_valid&&descriptor_ready)begin
  if(checking)begin
   $fwrite(observed,"%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n",jid,cfg_ic,cfg_oc,cfg_oh,cfg_ow,first_block,final_block,input_full_h,input_full_w,input_origin_y,input_origin_x,input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch,output_tail_owned);
   scan=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",ex[0],ex[1],ex[2],ex[3],ex[4],ex[5],ex[6],ex[7],ex[8],ex[9],ex[10],ex[11],ex[12],ex[13],ex[14],ex[15],ex[16],ex[17],ex[18]);
   if(scan!=19)$fatal(1,"missing expected descriptor");
   if(cfg_ic!==ex[0]||cfg_oc!==ex[1]||cfg_oh!==ex[2]||cfg_ow!==ex[3]||first_block!==ex[4][0]||final_block!==ex[5][0]||input_full_h!==ex[6]||input_full_w!==ex[7]||input_origin_y!==ex[8]||input_origin_x!==ex[9]||input_base!==ex[10]||input_row_pitch!==ex[11]||input_channel_pitch!==ex[12]||weight_base!==ex[13]||weight_oc_stride!==ex[14]||output_base!==ex[15]||output_row_pitch!==ex[16]||output_channel_pitch!==ex[17]||output_tail_owned!==ex[18][0]||cfg_kernel!==1||cfg_stride!==1)
    $fatal(1,"descriptor mismatch job%0d index%0d ic%0d oc%0d oh%0d input%h weight%h output%h",jid,idx,cfg_ic,cfg_oc,cfg_oh,input_base,weight_base,output_base);
  end
  if(tile_busy||tile_done)$fatal(1,"reuse active/sticky loader");
  tile_busy<=1;timer<=2+(cycle_count%4);saved_final<=final_block;seen<=seen+1;idx<=idx+1;
 end
 if(reset_n&&result_valid&&busy)$fatal(1,"early publication");
end
task cycle;begin @(posedge clk);#1;end endtask
task reset_all;begin
 @(negedge clk);reset_n=0;abort=0;clear=0;job_valid=0;out_ready=0;memory_ready=1;repeat(3)cycle;
 @(negedge clk);reset_n=1;cycle;
end endtask
task launch;begin
 t=0;while(!job_ready&&t<20)begin cycle;t=t+1;end
 if(!job_ready)$fatal(1,"job not ready");
 @(negedge clk);job_valid=1;cycle;@(negedge clk);job_valid=0;
end endtask
task wait_output;begin
 t=0;while(!out_valid&&t<2000000)begin cycle;t=t+1;end
 if(!out_valid)$fatal(1,"output timeout state%0d",dut.state);
end endtask
task consume;begin
 hold_count=completed_tiles;repeat(4)begin cycle;if(!out_valid||job_ready||completed_tiles!==hold_count)$fatal(1,"output backpressure");end
 @(negedge clk);out_ready=1;cycle;@(negedge clk);out_ready=0;
end endtask
initial begin
 reset_all;observed=$fopen("D:/GitHub/airpocket-soundman/tab5-tang-primer20k-carrier-resume-20261106/fpga/build/npu-ddr-matmul-sequencer/observed.txt","w");f=$fopen("D:/GitHub/airpocket-soundman/tab5-tang-primer20k-carrier-resume-20261106/fpga/build/npu-ddr-matmul-sequencer/jobs.txt","r");if(!f)$fatal(1,"jobs missing");
 while(!$feof(f))begin
  scan=$fscanf(f,"%d %d %d %d %d %d %d %d %d %d %d %d\n",jid,job_m,job_k,job_n,job_a_base,job_a_pitch,job_b_base,job_b_pitch,job_c_base,job_c_pitch,nexp,expected_error);
  if(scan==12)begin
   idx=0;checking=1;launch;wait_output;checking=0;
   if(error_code!==expected_error||error!==(expected_error!=0))$fatal(1,"job%0d error%0d expected%0d",jid,error_code,expected_error);
   if(expected_error==0)begin
    if(!result_valid||idx!=nexp||accepted_tiles!=nexp||completed_tiles!=nexp||expected_tiles!=nexp)$fatal(1,"counts/publication job%0d",jid);
   end else if(result_valid||accepted_tiles!=0||idx!=0)$fatal(1,"invalid job published or issued");
   consume;
   if(expected_error!=0)begin
    if(job_ready)$fatal(1,"error not latched");@(negedge clk);clear=1;cycle;@(negedge clk);clear=0;
   end
   jobs=jobs+1;total=total+idx;
  end
 end
 // Hostile loader cases, independent of descriptor file.
 job_m=197;job_k=17;job_n=9;job_a_base=0;job_a_pitch=208;job_b_base=1048576;job_b_pitch=32;job_c_base=2097152;job_c_pitch=832;
 for(i=1;i<=8;i=i+1)begin
  mode=i;reset_all;idx=0;launch;
  if(i==4)begin wait(accepted_tiles==1);@(negedge clk);abort=1;cycle;@(negedge clk);abort=0;end
  if(i==7)begin repeat(5)cycle;@(negedge clk);memory_ready=0;end
  if(i==8)begin repeat(5)cycle;@(negedge clk);abort=1;job_valid=1;out_ready=1;cycle;@(negedge clk);abort=0;job_valid=0;out_ready=0;end
  wait_output;
  if(!error||result_valid)$fatal(1,"faultmode%0d published numeric",i);
  if(i==1&&error_code!=4)$fatal(1,"loader error code");
  if(i==2&&(!quarantined||error_code!=8))$fatal(1,"quarantine lost");
  if(i==3&&(!quarantined||error_code!=6))$fatal(1,"timeout drain quarantine");
  if((i==4||i==8)&&error_code!=5)$fatal(1,"abort lost");
  if(i==5&&error_code!=9)$fatal(1,"missing final result");
  if(i==6&&error_code!=6)$fatal(1,"backpressure timeout");
  if(i==7&&error_code!=7)$fatal(1,"calibration loss");
  consume;
  if(i==2||i==3)begin @(negedge clk);clear=1;cycle;@(negedge clk);clear=0;if(job_ready||!quarantined)$fatal(1,"quarantine cleared without reset");end
 end
 // Recover an aborted validation without resetting the sequencer: no stale multiplier result.
 mode=0;@(negedge clk);clear=1;cycle;@(negedge clk);clear=0;
 launch;wait_output;if(error||!result_valid||completed_tiles!=4)$fatal(1,"restart after cleared validation abort");consume;
 // Validation reset/abort must not allow an old multiply to poison next job.
 mode=0;reset_all;launch;repeat(10)cycle;@(negedge clk);reset_n=0;cycle;@(negedge clk);reset_n=1;cycle;
 if(out_valid||result_valid||accepted_tiles)$fatal(1,"reset stale");
 launch;wait_output;if(error||!result_valid||completed_tiles!=4)$fatal(1,"restart after reset");consume;
 // Stale done must not count as completion or launch a tile.
 reset_all;tile_done=1;sticky=12;launch;repeat(8)cycle;if(accepted_tiles)$fatal(1,"stale done accepted");
 wait_output;if(error||completed_tiles!=4)$fatal(1,"sticky done recovery");consume;
 // A published result becomes invalid on calibration loss.
 reset_all;launch;wait_output;if(!result_valid)$fatal(1,"missing result");
 @(negedge clk);memory_ready=0;cycle;if(result_valid||!error||error_code!=7)$fatal(1,"old result survived calibration loss");
 // Abort dominates simultaneous new job acceptance.
 reset_all;@(negedge clk);abort=1;job_valid=1;out_ready=1;cycle;if(busy||accepted_tiles||out_valid)$fatal(1,"abort input priority");
 @(negedge clk);abort=0;job_valid=0;out_ready=0;
 $display("PASS DDR MatMul sequencer jobs=%0d descriptors=%0d plus8faults/reset/sticky/backpressure",jobs,total);$finish;
end
initial begin #2000000000;$fatal(1,"watchdog");end
endmodule
