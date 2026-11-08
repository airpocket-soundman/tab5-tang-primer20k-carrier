// Experimental autonomous profile: a RUN lease covers CPU, cache and MAC drain.
// Status polling is sideband only and never borrows the shared DDR staging RAM.
module npu_local_run_control(
 input wire clk,reset_n,arm,memory_ready,input wire[15:0] epoch,
 input wire start,abort,clear,input wire arb_active,arb_fault,mac_busy,mac_quarantined,
 input wire cpu_safe_to_release,cpu_fault,cpu_trap,input wire[3:0] cpu_error_code,
 input wire[31:0] cpu_node,cpu_stage,cpu_app_error,cpu_finish,
 output reg run_enable,abort_level,output wire start_ready,
 output reg done,error,aborted,output wire quarantined,output wire[15:0] status,
 input wire[5:0] monitor_index,output reg[31:0] monitor_data
);
 reg trap_seen;reg[15:0] saved_epoch;
 reg[31:0] node,stage,app_error,finish,run_id;reg[3:0] fault_code;
 reg[63:0] cycles;
 wire quiet=!arb_active&&!mac_busy;
 assign quarantined=arb_fault||mac_quarantined;
 assign start_ready=reset_n&&arm&&memory_ready&&!run_enable&&!done&&!aborted&&!error&&!quarantined&&quiet&&cpu_safe_to_release;
 assign status={8'd0,start_ready,aborted,trap_seen,quarantined,error,done,run_enable,memory_ready};
 always @*begin
  case(monitor_index)
   0:monitor_data={16'd0,status};1:monitor_data=node;2:monitor_data=stage;
   3:monitor_data=app_error;4:monitor_data=finish;5:monitor_data={28'd0,fault_code};
   6:monitor_data={16'd0,saved_epoch};7:monitor_data=run_id;
   8:monitor_data=cycles[31:0];9:monitor_data=cycles[63:32];
   default:monitor_data=0;
  endcase
 end
 always @(posedge clk)begin
  if(!reset_n||!arm)begin
   run_enable<=0;abort_level<=0;done<=0;error<=0;aborted<=0;trap_seen<=0;
   saved_epoch<=0;node<=0;stage<=0;app_error<=0;finish<=0;run_id<=0;fault_code<=0;cycles<=0;
  end else begin
   if(clear&&!run_enable&&quiet)begin
    abort_level<=0;done<=0;error<=0;aborted<=0;trap_seen<=0;
    node<=0;stage<=0;app_error<=0;finish<=0;fault_code<=0;
   end
   if(start&&start_ready)begin
    run_enable<=1;abort_level<=0;done<=0;error<=0;aborted<=0;trap_seen<=0;
    saved_epoch<=epoch;node<=0;stage<=0;app_error<=0;finish<=0;fault_code<=0;
    run_id<=run_id+1'b1;cycles<=0;
   end
   if(run_enable)begin
    cycles<=cycles+1'b1;node<=cpu_node;stage<=cpu_stage;app_error<=cpu_app_error;finish<=cpu_finish;
    if(abort||!memory_ready||epoch!=saved_epoch||arb_fault||cpu_fault||cpu_trap||mac_quarantined)begin
     abort_level<=1;error<=1;done<=0;aborted<=abort||aborted;
     trap_seen<=cpu_trap||trap_seen;fault_code<=cpu_error_code;
    end
    // CPU FINISH is visible only after its writeback barrier. An abort on the
    // same clock dominates successful completion, even when all engines drain.
    if((cpu_finish!=0||abort_level||abort||cpu_fault||cpu_trap||!memory_ready||epoch!=saved_epoch)&&cpu_safe_to_release&&quiet)begin
     run_enable<=0;
     if(cpu_finish==1&&!abort_level&&!abort&&!error&&!cpu_fault&&!cpu_trap&&!quarantined&&memory_ready&&epoch==saved_epoch&&cpu_app_error==0)done<=1;
     else begin done<=0;error<=1;end
    end
   end
  end
 end
endmodule
