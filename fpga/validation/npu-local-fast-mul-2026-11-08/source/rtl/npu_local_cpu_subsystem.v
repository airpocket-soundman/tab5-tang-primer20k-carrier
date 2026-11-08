// Experimental FPGA-local firmware executor. Not connected to deployed 4E24.
// COMMAND stores block the CPU across flush -> accelerator -> invalidate.
module npu_local_cpu_subsystem #(
 parameter ENABLE_MATRIX=1,CPU_FAST_MUL=0,
 parameter[31:0]BOOT_ADDR=32'h05000000,
 parameter MEMORY_TIMEOUT=2700000,DRAIN_TIMEOUT=2700000,MAC_TIMEOUT=1620000000
)(
 input wire clk,reset_n,memory_ready,run_enable,abort,clear,input wire[15:0]epoch,
 output wire cpu_trap,cpu_fault,output wire[3:0]cpu_error_code,
 output reg[31:0]progress_node,progress_stage,app_error,finish_code,
 output wire safe_to_release,
 output reg tile_start,output wire[415:0]tile_descriptor,output reg tile_clear,
 input wire tile_start_ready,tile_busy,tile_done,tile_error,tile_quarantined,tile_result_valid,input wire[3:0]tile_error_code,
 output reg matrix_start,output wire[287:0]matrix_job,output reg matrix_done_ack,
 input wire matrix_start_ready,matrix_busy,matrix_done,matrix_error,matrix_quarantined,matrix_result_valid,input wire[3:0]matrix_error_code,
 output wire req_t,cancel_t,output wire[1:0]h_op,output wire[31:0]h_addr,h_arg,
 output wire[15:0]h_beats,output wire[23:0]h_tag,
 input wire done_t,input wire[23:0]r_tag,input wire[3:0]r_status,input wire[15:0]r_beats,
 output wire w_we,output wire[7:0]w_addr,output wire[127:0]w_data,
 output wire[7:0]r_addr,input wire[127:0]r_data
);
 localparam IDLE=0,RESPONSE=1,PRE=2,PRE_RELEASE=3,LAUNCH=4,MAC_WAIT=5,POST=6,POST_RELEASE=7,FINISH=8,FINISH_RELEASE=9;
 reg[3:0]state;reg[31:0]mmio_rdata,operation,mac_timer,pending_finish;
 reg done_flag,error_flag,valid_flag,quarantine_flag,halted,trap_latched,abort_latched;
 reg[3:0]mac_error;reg[415:0]descriptor;
 wire native_valid,native_instr,native_ready,core_trap;wire[31:0]native_addr,native_wdata,native_rdata;wire[3:0]native_wstrb;
 wire is_mmio=native_addr[31:8]==24'h100000;
 wire cache_ready,cache_error,cache_quarantine,cache_idle,barrier_done;wire[3:0]cache_code;wire[31:0]cache_rdata;
 wire barrier=state==PRE||state==POST||state==FINISH;
 wire stopped=halted||abort_latched||trap_latched||cache_error||quarantine_flag;
 wire core_reset_n=reset_n&&run_enable&&!stopped&&!abort;
 wire mmio_ready=state==RESPONSE&&native_valid&&is_mmio&&!abort&&!cache_error&&memory_ready;
 assign native_ready=is_mmio?mmio_ready:cache_ready;
 assign native_rdata=is_mmio?mmio_rdata:cache_rdata;
 assign tile_descriptor=descriptor;assign matrix_job=ENABLE_MATRIX?descriptor[287:0]:288'd0;
 assign cpu_trap=trap_latched;assign cpu_fault=cache_error||trap_latched||abort_latched||quarantine_flag;
 assign cpu_error_code=cache_error?cache_code:trap_latched?4'hf:abort_latched?4'h8:mac_error;
 assign safe_to_release=(!run_enable||stopped)&&cache_idle&&!tile_busy&&(!ENABLE_MATRIX||!matrix_busy)&&!cache_quarantine&&!tile_quarantined&&(!ENABLE_MATRIX||!matrix_quarantined)&&!quarantine_flag;
 wire csr_busy=state>=PRE&&state<=POST_RELEASE;
 wire csr_ready=state==IDLE&&!done_flag&&!error_flag&&!quarantine_flag&&memory_ready&&tile_start_ready&&(!ENABLE_MATRIX||matrix_start_ready);
 wire[31:0]status_word={25'd0,memory_ready,valid_flag,quarantine_flag,error_flag,done_flag,csr_busy,csr_ready};
 picorv32 #(.ENABLE_COUNTERS(0),.ENABLE_COUNTERS64(0),.COMPRESSED_ISA(1),.ENABLE_MUL(1),.ENABLE_FAST_MUL(CPU_FAST_MUL),.ENABLE_DIV(1),
  .ENABLE_IRQ(0),.ENABLE_IRQ_QREGS(0),.ENABLE_IRQ_TIMER(0),.PROGADDR_RESET(BOOT_ADDR),.CATCH_MISALIGN(1),.CATCH_ILLINSN(1)) cpu(
  .clk(clk),.resetn(core_reset_n),.trap(core_trap),.mem_valid(native_valid),.mem_instr(native_instr),.mem_ready(native_ready),
  .mem_addr(native_addr),.mem_wdata(native_wdata),.mem_wstrb(native_wstrb),.mem_rdata(native_rdata),
  .pcpi_wr(1'b0),.pcpi_rd(32'd0),.pcpi_wait(1'b0),.pcpi_ready(1'b0),.irq(32'd0));
 npu_rv32_ddr_cache #(.MEMORY_TIMEOUT(MEMORY_TIMEOUT),.DRAIN_TIMEOUT(DRAIN_TIMEOUT)) memory(
  .clk(clk),.reset_n(reset_n),.memory_ready(memory_ready),.permit(run_enable&&!halted),.abort(abort||abort_latched||trap_latched),.clear(clear),
  .mem_valid(native_valid&&!is_mmio&&run_enable&&!stopped),.mem_instr(native_instr),.mem_addr(native_addr),.mem_wdata(native_wdata),.mem_wstrb(native_wstrb),
  .mem_ready(cache_ready),.mem_rdata(cache_rdata),.barrier_valid(barrier),.barrier_done(barrier_done),.error(cache_error),.quarantined(cache_quarantine),.error_code(cache_code),.idle(cache_idle),
  .req_t(req_t),.cancel_t(cancel_t),.h_op(h_op),.h_addr(h_addr),.h_arg(h_arg),.h_beats(h_beats),.h_tag(h_tag),
  .done_t(done_t),.r_tag(r_tag),.r_status(r_status),.r_beats(r_beats),.w_we(w_we),.w_addr(w_addr),.w_data(w_data),.r_addr(r_addr),.r_data(r_data));
 integer i;
 always @(posedge clk)begin
  tile_start<=0;matrix_start<=0;matrix_done_ack<=0;tile_clear<=0;
  if(!reset_n)begin
   state<=IDLE;mmio_rdata<=0;operation<=0;mac_timer<=0;pending_finish<=0;
   done_flag<=0;error_flag<=0;valid_flag<=0;quarantine_flag<=0;mac_error<=0;descriptor<=0;
   halted<=0;trap_latched<=0;abort_latched<=0;progress_node<=0;progress_stage<=0;app_error<=0;finish_code<=0;
  end else begin
   if(core_trap&&run_enable)trap_latched<=1;
   if(abort)abort_latched<=1;
   if(clear&&!run_enable&&cache_idle&&!cache_quarantine&&!tile_busy&&(!ENABLE_MATRIX||!matrix_busy))begin
    state<=IDLE;done_flag<=0;error_flag<=0;valid_flag<=0;quarantine_flag<=0;mac_error<=0;halted<=0;trap_latched<=0;abort_latched<=0;
    finish_code<=0;progress_node<=0;progress_stage<=0;app_error<=0;tile_clear<=1;if(ENABLE_MATRIX)matrix_done_ack<=1;
   end else if(!stopped&&!abort&&memory_ready)case(state)
    IDLE:if(native_valid&&is_mmio)begin
     if(native_addr[1:0]!=0)begin error_flag<=1;mac_error<=1;state<=RESPONSE;end
     else if(native_wstrb==0)begin
      case(native_addr[7:0])
       0:mmio_rdata<=status_word;16:mmio_rdata<={28'd0,mac_error};24:mmio_rdata<={16'd0,epoch};
       32:mmio_rdata<=progress_node;36:mmio_rdata<=progress_stage;40:mmio_rdata<=app_error;44:mmio_rdata<=finish_code;
       default:if(native_addr[7:0]>=64&&native_addr[7:0]<=112)mmio_rdata<=descriptor[(native_addr[7:0]-64)*8+:32];
        else begin mmio_rdata<=0;error_flag<=1;mac_error<=1;end
      endcase
      state<=RESPONSE;
     end else if(native_wstrb!=15)begin error_flag<=1;mac_error<=1;state<=RESPONSE;end
     else case(native_addr[7:0])
      4:begin
       if(!done_flag&&!error_flag&&!quarantine_flag&&(native_wdata==1||(ENABLE_MATRIX&&native_wdata==2)))begin operation<=ENABLE_MATRIX?native_wdata:32'd1;state<=PRE;mac_timer<=0;end
       else begin error_flag<=1;mac_error<=2;state<=RESPONSE;end
      end
      8:begin
       if(native_wdata==1)begin done_flag<=0;valid_flag<=0;if(!quarantine_flag)begin error_flag<=0;mac_error<=0;end
        if(ENABLE_MATRIX&&operation==2)matrix_done_ack<=1;
       end else begin error_flag<=1;mac_error<=1;end
       state<=RESPONSE;
      end
      12:begin error_flag<=1;mac_error<=8;state<=RESPONSE;end
      32:begin progress_node<=native_wdata;state<=RESPONSE;end
      36:begin progress_stage<=native_wdata;state<=RESPONSE;end
      40:begin app_error<=native_wdata;state<=RESPONSE;end
      44:begin
       if(native_wdata==1||native_wdata==2)begin pending_finish<=native_wdata==1&&(error_flag||app_error!=0)?32'd2:native_wdata;state<=FINISH;end
       else begin error_flag<=1;mac_error<=1;state<=RESPONSE;end
      end
      default:begin
       if(native_addr[7:0]>=64&&native_addr[7:0]<=112)begin
        for(i=0;i<13;i=i+1)if(native_addr[7:0]==64+i*4)descriptor[i*32+:32]<=native_wdata;
       end
       else begin error_flag<=1;mac_error<=1;end
       state<=RESPONSE;
      end
     endcase
    end
    RESPONSE:state<=IDLE;
    PRE:if(barrier_done)state<=PRE_RELEASE;
    PRE_RELEASE:state<=LAUNCH;
    LAUNCH:begin
     if((operation==1&&tile_start_ready)||(ENABLE_MATRIX&&operation==2&&matrix_start_ready))begin
      if(operation==1)tile_start<=1;else if(ENABLE_MATRIX)matrix_start<=1;state<=MAC_WAIT;mac_timer<=0;
     end else if(mac_timer>=MAC_TIMEOUT)begin error_flag<=1;mac_error<=3;done_flag<=1;state<=POST;end
     else mac_timer<=mac_timer+1'b1;
    end
    MAC_WAIT:begin
     if((operation==1&&tile_done)||(ENABLE_MATRIX&&operation==2&&matrix_done))begin
      done_flag<=1;error_flag<=operation==1?tile_error:matrix_error;quarantine_flag<=operation==1?tile_quarantined:matrix_quarantined;
      valid_flag<=operation==1?tile_result_valid:matrix_result_valid;mac_error<=operation==1?tile_error_code:matrix_error_code;state<=POST;
     end else if((operation==1&&tile_error)||(ENABLE_MATRIX&&operation==2&&matrix_error))begin
      done_flag<=1;error_flag<=1;quarantine_flag<=operation==1?tile_quarantined:matrix_quarantined;valid_flag<=0;
      mac_error<=operation==1?tile_error_code:matrix_error_code;state<=POST;
     end else if(mac_timer>=MAC_TIMEOUT)begin error_flag<=1;done_flag<=1;mac_error<=3;quarantine_flag<=1;state<=POST;end
     else mac_timer<=mac_timer+1'b1;
    end
    POST:if(!tile_busy&&(!ENABLE_MATRIX||!matrix_busy)&&barrier_done)state<=POST_RELEASE;
    POST_RELEASE:state<=RESPONSE;
    FINISH:if(barrier_done)state<=FINISH_RELEASE;
    FINISH_RELEASE:begin finish_code<=pending_finish;halted<=1;if(ENABLE_MATRIX&&operation==2)matrix_done_ack<=1;state<=IDLE;end
    default:begin error_flag<=1;mac_error<=4;halted<=1;end
   endcase
  end
 end
endmodule
