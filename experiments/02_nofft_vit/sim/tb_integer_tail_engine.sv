`timescale 1ns/1ps
module tb_integer_tail_engine;
    reg clk=0,reset=1,input_we=0,start=0,result_ready=0;
    always #5 clk=~clk;
    reg [7:0] input_addr=0;reg [15:0] input_data=0;
    wire ready,done,result_valid,result_sat,result_error;
    wire [5:0] result_index;wire signed [47:0] result_acc;wire signed [15:0] result_y;
    integer_tail_engine dut(.*);
    reg [15:0] xs[0:3071],zs[0:1535],gs[0:1535],ys[0:671];
    reg [47:0] pre_accs[0:1535],accs[0:671];
    integer sample_id=0,pre_count=0,out_count=0,i,cycles=0;
    reg checking=0,stalled=0;reg [71:0] held;
    always @(negedge clk) begin
        cycles=cycles+1;result_ready=(cycles%11)>3;
    end
    always @(posedge clk) if(!reset && checking) begin
        if(dut.pre_valid && dut.state==3) begin
            if(dut.pre_index!==pre_count || dut.pre_acc!==pre_accs[sample_id*96+pre_count] ||
                dut.pre_y!==zs[sample_id*96+pre_count] || dut.gelu_q!==gs[sample_id*96+pre_count] ||
                dut.pre_sat || dut.pre_error) $fatal(1,"Intermediate mismatch sample=%0d output=%0d",sample_id,pre_count);
            pre_count=pre_count+1;
        end
        if(stalled && (!result_valid || {result_index,result_acc,result_y,result_sat,result_error}!==held))
            $fatal(1,"Output changed under backpressure");
        stalled=result_valid && !result_ready;
        held={result_index,result_acc,result_y,result_sat,result_error};
        if(result_valid && result_ready) begin
            if(result_index!==out_count || result_acc!==accs[sample_id*42+out_count] ||
                result_y!==ys[sample_id*42+out_count] || result_sat || result_error)
                $fatal(1,"Final mismatch sample=%0d output=%0d",sample_id,out_count);
            out_count=out_count+1;
        end
    end
    task load_and_start;
        begin
            wait(ready);
            for(i=0;i<192;i=i+1) begin
                @(negedge clk);input_we=1;input_addr=i;input_data=xs[sample_id*192+i];
            end
            @(negedge clk);input_we=0;start=1;
            @(negedge clk);start=0;
        end
    endtask
    initial begin
        $readmemh("test_inputs.mem",xs);$readmemh("test_pre_acc.mem",pre_accs);
        $readmemh("test_pre_codes.mem",zs);$readmemh("test_gelu_codes.mem",gs);
        $readmemh("test_acc.mem",accs);$readmemh("test_outputs.mem",ys);
        repeat(4) @(negedge clk);reset=0;
        // Abort an operation; then overwrite every input and prove normal recovery.
        load_and_start();repeat(100) @(negedge clk);reset=1;
        repeat(4) @(negedge clk);reset=0;
        if(!ready || result_valid || done) $fatal(1,"Reset did not abort operation");
        for(sample_id=0;sample_id<16;sample_id=sample_id+1) begin
            pre_count=0;out_count=0;stalled=0;checking=1;load_and_start();
            wait(done);@(negedge clk);checking=0;
            if(pre_count!=96 || out_count!=42) $fatal(1,"Wrong result count");
        end
        $display("PASS: 16 runtime vectors, 1536 intermediate MAC/GELU values, 672 final records, output stalls and reset abort");$finish;
    end
    initial begin repeat(1000000) @(posedge clk);$fatal(1,"Timeout");end
endmodule
