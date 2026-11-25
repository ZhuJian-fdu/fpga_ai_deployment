`timescale 1ns/1ps
module tb_acx720_v3_heartbeat;
    reg clk=0, reset_n=1;
    wire led0;
    always #5 clk=~clk;
    acx720_v3_heartbeat_top #(.CLK_HZ(8)) dut(.*);
    integer n;
    task check_blink;
        begin
            // Two clocks release the reset synchronizer; heartbeat still sees reset.
            repeat(2) @(negedge clk);
            if (led0 !== 0) $fatal(1, "LED must be off during reset release");
            for(n=1;n<=16;n=n+1) begin
                @(negedge clk);
                if (led0 !== ((n/4)%2)) $fatal(1, "wrong LED phase/cadence");
            end
        end
    endtask
    initial begin
        check_blink(); // FPGA power-on INIT; S4 not pressed
        // Assert S4 between clock edges, hold it and verify LED remains off.
        #2 reset_n=0;
        repeat(3) begin
            @(negedge clk);
            if (led0 !== 0) $fatal(1, "S4 did not reset LED");
        end
        #2 reset_n=1;
        check_blink();
        $display("PASS: ACX720-V3 startup, S4 reset, synchronous release and LED cadence.");
        $finish;
    end
endmodule
