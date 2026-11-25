`timescale 1ns/1ps
module tb_heartbeat;
    reg clk=0, rst=1;
    wire led;
    integer cycle;
    always #5 clk=~clk;
    heartbeat #(.CLK_HZ(8)) dut(.clk(clk), .rst(rst), .led(led));
    initial begin
        repeat(2) @(negedge clk);
        if (led !== 0) $fatal(1, "reset failed");
        rst=0;
        for (cycle=1; cycle<=24; cycle=cycle+1) begin
            @(negedge clk);
            if (led !== ((cycle/4)%2)) $fatal(1, "wrong LED period");
        end
        rst=1;
        @(negedge clk);
        if (led !== 0) $fatal(1, "second reset failed");
        $display("PASS: heartbeat period and reset.");
        $finish;
    end
endmodule
