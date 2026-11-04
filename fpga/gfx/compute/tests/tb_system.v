// compute_simd + compute_mem_adapter + fault-injecting backend. Two jobs are run
// back to back (job A at entry 0, job B at entry 32). See run_compute.py.
`timescale 1ns/1ps
module tb_system;
    parameter LANES=2;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1, program_we=0, start=0, flush=0;
    reg [7:0] program_addr=0;
    reg [31:0] program_data=0, group_base=0, instruction_limit=10000, element_count=0;
    reg [15:0] entry=0;
    wire busy,done,mem_valid,mem_write,rsp_ready,rsp_valid,rsp_error;
    wire [3:0] error,mem_wmask;
    wire [31:0] cycles,instructions,groups,mem_word_addr,mem_wdata,rsp_data;
    wire be_valid,be_write; wire [31:0] be_addr,be_wdata; wire [3:0] be_wmask;
    reg be_rsp_valid=0,be_rsp_error=0; reg [31:0] be_rsp_data=0;
    wire mem_ready;
    wire [15:0] orphans; wire [31:0] violations,timeouts;
    reg [31:0] timeout_cycles=0, rlimit=256;
    reg be_busy=0;
    wire be_ready = !be_busy;

    compute_simd #(.LANES(LANES)) dut(.*);
    compute_mem_adapter #(.REGIONS(2)) adapter(
        .clk(clk),.reset(reset),.flush(flush),.timeout_cycles(timeout_cycles),
        .region_base({32'd0,32'd0}),.region_limit({32'd0,rlimit}),.region_perm({2'b00,2'b11}),
        .mem_valid(mem_valid),.mem_ready(mem_ready),.mem_write(mem_write),
        .mem_word_addr(mem_word_addr),.mem_wdata(mem_wdata),.mem_wmask(mem_wmask),
        .rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.rsp_data(rsp_data),.rsp_error(rsp_error),
        .be_valid(be_valid),.be_ready(be_ready),.be_write(be_write),.be_addr(be_addr),
        .be_wdata(be_wdata),.be_wmask(be_wmask),.be_rsp_valid(be_rsp_valid),
        .be_rsp_data(be_rsp_data),.be_rsp_error(be_rsp_error),
        .orphans(orphans),.violations(violations),.timeouts(timeouts));

    reg [31:0] memory[0:255], code[0:255], present[0:255], exp_a[0:255], exp_b[0:255];
    reg hung=0, hang_armed=1, cur_write=0, cur_err=0;
    reg [31:0] cur_addr=0, cur_data=0, byte_mask;
    reg [3:0] cur_mask=0;
    integer lat_left=0, req_no=0, mode, idx, late;
    integer exp_err_a, exp_err_b, exp_orph_a, exp_to_a, exp_viol_a, b_stalls, backend_writes_hi=0;
    integer j, k, cap;
    reg [4095:0] directory;

    always @(posedge clk) begin
        if (reset) begin be_busy<=0; be_rsp_valid<=0; req_no<=0; end
        else begin
            be_rsp_valid<=0; be_rsp_error<=0;
            if (be_valid && be_ready) begin
                be_busy<=1; cur_write<=be_write; cur_addr<=be_addr; cur_data<=be_wdata; cur_mask<=be_wmask;
                cur_err<=(mode==2 && req_no==idx);
                req_no<=req_no+1;
                if (mode==1 && req_no==idx && hang_armed) begin hung<=1; lat_left<=late; end
                else begin hung<=0; lat_left<=3; end
            end
            if (be_busy && !(hung && late==0)) begin
                if (lat_left!=0) lat_left<=lat_left-1;
                else begin
                    be_busy<=0; be_rsp_valid<=1; be_rsp_error<=cur_err; be_rsp_data<=0;
                    if (!cur_err) begin
                        if (cur_write) begin
                            byte_mask={{8{cur_mask[3]}},{8{cur_mask[2]}},{8{cur_mask[1]}},{8{cur_mask[0]}}};
                            memory[cur_addr]<=(memory[cur_addr]&~byte_mask)|(cur_data&byte_mask);
                            if (cur_addr>=rlimit) backend_writes_hi<=backend_writes_hi+1;
                        end else be_rsp_data<=memory[cur_addr];
                    end
                end
            end
        end
    end

    task write_program; input [7:0] address; input [31:0] value;
        begin @(negedge clk); program_we=1; program_addr=address; program_data=value;
              @(negedge clk); program_we=0; end
    endtask
    task load_programs;
        begin for (j=0;j<256;j=j+1) if (present[j]) write_program(j,code[j]); end
    endtask
    task run_job; input [15:0] at;
        begin
            @(negedge clk); flush=1; @(negedge clk); flush=0;
            entry=at; @(negedge clk); start=1; @(negedge clk); start=0;
            cap=0;
            while(!done && cap<4000) begin @(negedge clk); cap=cap+1; end
        end
    endtask
    task check_memory; input [31:0] which; input integer first_bad;
        begin
            for (k=0;k<256;k=k+1)
                if (memory[k]!==(which==0 ? exp_a[k] : exp_b[k]))
                    $fatal(1,"memory[%0d]=%h expected=%h after job %0d",k,memory[k],which==0 ? exp_a[k] : exp_b[k],which);
        end
    endtask

    initial begin
        if (!$value$plusargs("directory=%s",directory)) $fatal(1,"directory missing");
        if (!$value$plusargs("mode=%d",mode)) $fatal(1,"mode missing");
        if (!$value$plusargs("idx=%d",idx)) $fatal(1,"idx missing");
        if (!$value$plusargs("late=%d",late)) $fatal(1,"late missing");
        if (!$value$plusargs("timeout=%d",timeout_cycles)) $fatal(1,"timeout missing");
        if (!$value$plusargs("rlimit=%d",rlimit)) $fatal(1,"rlimit missing");
        if (!$value$plusargs("err_a=%d",exp_err_a)) $fatal(1,"err_a missing");
        if (!$value$plusargs("err_b=%d",exp_err_b)) $fatal(1,"err_b missing");
        if (!$value$plusargs("orph_a=%d",exp_orph_a)) $fatal(1,"orph_a missing");
        if (!$value$plusargs("to_a=%d",exp_to_a)) $fatal(1,"to_a missing");
        if (!$value$plusargs("viol_a=%d",exp_viol_a)) $fatal(1,"viol_a missing");
        if (!$value$plusargs("b_stalls=%d",b_stalls)) $fatal(1,"b_stalls missing");
        $readmemh({directory,"/program.hex"},code);
        $readmemh({directory,"/present.hex"},present);
        $readmemh({directory,"/input.hex"},memory);
        $readmemh({directory,"/exp_a.hex"},exp_a);
        $readmemh({directory,"/exp_b.hex"},exp_b);
        repeat(3) @(negedge clk);
        reset=0;
        load_programs;
        run_job(0);
        if (!done) $fatal(1,"job A did not finish");
        if (error!==exp_err_a[3:0]) $fatal(1,"job A error=%0d expected=%0d",error,exp_err_a);
        if (orphans!==exp_orph_a[15:0]) $fatal(1,"orphans=%0d expected=%0d",orphans,exp_orph_a);
        if (timeouts!==exp_to_a[31:0]) $fatal(1,"timeouts=%0d expected=%0d",timeouts,exp_to_a);
        if (violations!==exp_viol_a[31:0]) $fatal(1,"violations=%0d expected=%0d",violations,exp_viol_a);
        // Memory after job A is checked once the backend is idle again (late writes land first).
        if (b_stalls==0 && exp_orph_a==0) check_memory(0,0);
        run_job(32);
        if (b_stalls) begin
            if (done || !busy) $fatal(1,"job B must stall behind a never-answered orphan");
            if (orphans!==1) $fatal(1,"orphan lost");
            // recovery: reset core+adapter+backend together, reload code, rerun B
            reset=1; hang_armed=0; repeat(3) @(negedge clk); reset=0;
            load_programs;
            run_job(32);
            if (!done) $fatal(1,"job B after reset did not finish");
        end else if (!done) $fatal(1,"job B did not finish");
        if (error!==exp_err_b[3:0]) $fatal(1,"job B error=%0d expected=%0d",error,exp_err_b);
        repeat(8) @(negedge clk);
        if (orphans!==0) $fatal(1,"orphans left=%0d",orphans);
        if (exp_err_b==0 || exp_err_b==4) check_memory(1,0);
        if (rlimit<256 && backend_writes_hi!=0) $fatal(1,"backend saw %0d writes outside the region",backend_writes_hi);
        $display("PASS system mode=%0d timeouts=%0d violations=%0d",mode,timeouts,violations);
        $finish;
    end
    initial begin #20000000; $fatal(1,"system timeout"); end
endmodule
