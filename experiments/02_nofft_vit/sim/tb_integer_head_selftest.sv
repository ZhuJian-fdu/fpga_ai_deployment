`timescale 1ns/1ps
module tb_integer_head_selftest;
    parameter CASE=0;
    reg clk=0,reset=1;
    always #5 clk=~clk;
    wire done,failed;
    integer_head_selftest dut(.*);
    initial begin
        #1;
        if(CASE==1) dut.expected_out_mem[0]=dut.expected_out_mem[0]^16'b1;
        repeat(3) @(negedge clk);reset=0;
        if(CASE==2) begin
            repeat(500) @(negedge clk);reset=1;
            repeat(3) @(negedge clk);reset=0;
        end
        wait(done||failed);@(negedge clk);
        if(CASE==1) begin if(done || !failed) $fatal(1,"Injected corruption not detected");end
        else if(!done || failed) $fatal(1,"Reference vectors failed");
        repeat(10) @(negedge clk);
        if(CASE!=1 && (!done || failed)) $fatal(1,"Completion not held");
        $display("PASS: head selftest CASE=%0d done=%b failed=%b",CASE,done,failed);$finish;
    end
    initial begin repeat(300000) @(posedge clk);$fatal(1,"Timeout");end
endmodule
