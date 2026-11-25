`timescale 1ns/1ps
module tb_ai_reset;
    reg clk=0,reset_n=1,uart_rx=1;
    wire uart_tx,led0,led1,led2;
    always #5 clk=~clk;
    acx720_v3_ai_top dut(.*);
    initial begin
        repeat(3) @(negedge clk);
        if(dut.core_reset!==0) $fatal(1,"startup reset did not release");
        repeat(3) @(negedge clk);
        #2 reset_n=0;
        #1;
        if(dut.core_reset!==0) $fatal(1,"core reset asserted asynchronously");
        repeat(2) begin
            @(negedge clk);
            if(dut.core_reset!==0) $fatal(1,"reset bypassed synchronizer");
        end
        @(negedge clk);
        if(dut.core_reset!==1) $fatal(1,"core reset not asserted on clock");
        repeat(3) @(negedge clk);
        #2 reset_n=1;
        repeat(2) begin
            @(negedge clk);
            if(dut.core_reset!==1) $fatal(1,"reset released too early");
        end
        @(negedge clk);
        if(dut.core_reset!==0) $fatal(1,"reset failed to release");
        repeat(3) @(negedge clk);
        if(uart_tx!==1 || led1!==0 || led2!==0) $fatal(1,"idle outputs not reset");
        $display("PASS: AI top-level reset asserts/releases synchronously for BRAM controls.");
        $finish;
    end
endmodule
