
`timescale 1ns/1ps
module tb_ddr_loader;
 localparam CAP=262144;
 reg clk=0,reset_n=0,memory_ready=0,clear=0;
 wire start_ready,busy,block_done,result_valid,error,quarantined;

 wire[4:0]cfg_ic,cfg_oh,cfg_ow;wire[3:0]cfg_oc;wire[1:0]cfg_kernel,cfg_stride;
 wire first_block,final_block,output_tail_owned;
 wire[15:0]input_full_h,input_full_w;wire signed[31:0]input_origin_y,input_origin_x;
 wire[31:0]input_base,input_row_pitch,input_channel_pitch,weight_base,weight_oc_stride,output_base,output_row_pitch,output_channel_pitch;
 reg job_valid=0,out_ready=0;reg[575:0]job=0;
 wire job_ready,seq_busy,seq_out,seq_result,seq_error,seq_quarantine,desc_valid,abort;
 wire[3:0]seq_code;wire[31:0]accepted_tiles,completed_tiles,expected_tiles;wire[415:0]descriptor;
 wire start=desc_valid&&start_ready;
 assign cfg_ic=descriptor[0+:8];assign cfg_oc=descriptor[8+:8];assign cfg_oh=descriptor[16+:8];assign cfg_ow=descriptor[24+:8];
 assign cfg_kernel=descriptor[32+:8];assign cfg_stride=descriptor[40+:8];assign first_block=descriptor[48];assign final_block=descriptor[49];assign output_tail_owned=descriptor[50];
 assign input_full_h=descriptor[64+:16];assign input_full_w=descriptor[80+:16];
 assign input_origin_y=descriptor[96+:32];assign input_origin_x=descriptor[128+:32];assign input_base=descriptor[160+:32];
 assign input_row_pitch=descriptor[192+:32];assign input_channel_pitch=descriptor[224+:32];assign weight_base=descriptor[256+:32];
 assign weight_oc_stride=descriptor[288+:32];assign output_base=descriptor[320+:32];assign output_row_pitch=descriptor[352+:32];assign output_channel_pitch=descriptor[384+:32];
 npu_ddr_conv_strip_sequencer #(.CAPACITY(CAP),.TILE_TIMEOUT(500000))seq(
  .clk(clk),.reset_n(reset_n),.abort(1'b0),.clear(clear),.memory_ready(memory_ready),.job_valid(job_valid),.job_ready(job_ready),.job(job),
  .busy(seq_busy),.out_valid(seq_out),.out_ready(out_ready),.result_valid(seq_result),.error(seq_error),.quarantined(seq_quarantine),.error_code(seq_code),
  .accepted_tiles(accepted_tiles),.completed_tiles(completed_tiles),.expected_tiles(expected_tiles),.descriptor_valid(desc_valid),.descriptor_ready(start_ready),.descriptor(descriptor),
  .tile_busy(busy),.tile_done(block_done),.tile_error(error),.tile_quarantined(quarantined),.tile_result_valid(result_valid),.tile_abort(abort));
 wire[3:0]error_code,mem_status;wire[31:0]total_cycles,ddr_wait_cycles,read_beats,write_beats,kernel_cycles;
 wire req_t,cancel_t;wire[1:0]h_op;wire[31:0]h_addr,h_arg;wire[15:0]h_beats;wire[23:0]h_tag;
 reg done_t=0;reg[23:0]r_tag=0;reg[3:0]r_status=0;reg[15:0]r_beats=0;
 wire w_we;wire[7:0]w_addr,r_addr;wire[127:0]w_data;reg[127:0]r_data=0;
 reg[7:0]mem[0:CAP-1],shadow[0:CAP-1];reg[127:0]write_stage[0:255],read_stage[0:255];
 integer actor=0,mode=0,active_mode=0,delay_count=0,beat=0,requests=0,reads=0,writes=0;
 reg req_ref=0,cancel_ref=0;reg[1:0]saved_op;reg[31:0]saved_addr,saved_arg;reg[15:0]saved_beats;reg[23:0]saved_tag;reg[3:0]pending_status;reg[15:0]pending_beats;reg bad_sent=0;
 integer z,t;
 always #18.5 clk=~clk;
 npu_ddr_tile_loader_8oc #(.CAPACITY(CAP),.MEMORY_TIMEOUT(200),.DRAIN_TIMEOUT(100)) dut(.*);
 always @(posedge clk)begin
  if(w_we)write_stage[w_addr]<=w_data;r_data<=read_stage[r_addr];
  if(!reset_n)begin actor<=0;req_ref<=0;cancel_ref<=0;done_t<=0;r_tag<=0;r_status<=0;r_beats<=0;requests<=0;reads<=0;writes<=0;mode<=0;bad_sent<=0;end
  else begin
   if(actor!=0 && {h_op,h_addr,h_beats,h_arg,h_tag}!={saved_op,saved_addr,saved_beats,saved_arg,saved_tag})$fatal(1,"metadata changed before adapter drain");
   if(actor!=0 && req_t!=req_ref)$fatal(1,"overlapping memory request");
   if(actor!=0 && cancel_t!=cancel_ref && active_mode!=3 && active_mode!=7)begin
    cancel_ref<=cancel_t;pending_status<=8;pending_beats<=beat;actor<=3;
   end else case(actor)
    0:if(req_t!=req_ref)begin
     if(h_addr[3:0]!=0 || h_beats<1 || h_beats>256 || {1'b0,h_addr}+h_beats*16>CAP || h_op>1)$fatal(1,"invalid adapter request addr%h beats%d op%d",h_addr,h_beats,h_op);
     req_ref<=req_t;cancel_ref<=cancel_t;saved_op<=h_op;saved_addr<=h_addr;saved_beats<=h_beats;saved_arg<=h_arg;saved_tag<=h_tag;requests<=requests+1;beat<=0;bad_sent<=0;
     if(mode==5 && h_op!=1)active_mode<=0;else begin active_mode<=mode;mode<=0;end
     delay_count<=mode==4?50:5;actor<=1;
    end
    1:if(active_mode==3)begin end
      else if(delay_count!=0)delay_count<=delay_count-1;
      else if(active_mode==1)begin pending_status<=4;pending_beats<=0;actor<=3;end
      else actor<=2;
    2:begin
     if(saved_op==0)begin for(z=0;z<16;z=z+1)read_stage[beat][z*8+:8]<=mem[saved_addr+beat*16+z];reads<=reads+1;end
     else begin for(z=0;z<16;z=z+1)mem[saved_addr+beat*16+z]<=write_stage[beat][z*8+:8];writes<=writes+1;end
     beat<=beat+1;
     if(active_mode==5)begin pending_status<=4;pending_beats<=beat+1;actor<=3;end
     else if(beat+1==saved_beats)begin pending_status<=0;pending_beats<=active_mode==6?0:beat+1;actor<=3;end
    end
    3:begin
     done_t<=~done_t;r_status<=pending_status;r_beats<=pending_beats;
     if((active_mode==2 || active_mode==7) && !bad_sent)begin r_tag<=saved_tag^1;bad_sent<=1;actor<=4;end
     else begin r_tag<=saved_tag;actor<=0;end
    end
    4:begin end
   endcase
  end
 end

 integer f,j,i,rc,ticks,expected_count;reg[575:0]incoming;
 initial begin
  f=$fopen("real-jobs.txt","r");
  for(j=0;j<4;j=j+1)begin
   @(negedge clk);reset_n=0;memory_ready=0;job_valid=0;out_ready=0;
   repeat(5)@(negedge clk);
   $readmemh($sformatf("input_%0d.hex",j),mem);$readmemh($sformatf("expected_%0d.hex",j),shadow);
   rc=$fscanf(f,"%h %d\n",incoming,expected_count);if(rc!=2)$fatal(1,"real fixture parse");
   reset_n=1;memory_ready=1;repeat(5)@(negedge clk);
   if(!job_ready)$fatal(1,"seq not ready");job=incoming;job_valid=1;
   @(negedge clk);job_valid=0;job=0;ticks=0;
   while(!seq_out&&ticks<5000000)begin @(negedge clk);ticks=ticks+1;end
   if(!seq_out||!seq_result||seq_error||seq_quarantine||error||quarantined||accepted_tiles!=expected_count||completed_tiles!=expected_count)$fatal(1,"real loader status j%0d seq%0d loader%0d",j,seq_code,error_code);
   for(i=0;i<CAP;i=i+1)if(mem[i]!==shadow[i])$fatal(1,"real DDR mismatch job%0d addr%h got%h expected%h",j,i,mem[i],shadow[i]);
   $display("PASS actual8OC loader strip job%0d tiles%0d",j,completed_tiles);
  end
  $finish;
 end
 initial begin #3000000000;$fatal(1,"real global timeout");end
endmodule
