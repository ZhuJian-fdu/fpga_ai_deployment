`timescale 1ns/1ps
`include "sim_config.vh"
module tb_digit_classifier;
    reg clk=0;
    always #5 clk=~clk;
    reg rst=1, pixel_we=0, start=0;
    reg [5:0] pixel_addr=0;
    reg [7:0] pixel_data=0;
    wire busy, done, score_valid;
    wire [3:0] prediction, score_class;
    wire signed [31:0] score_value;
    digit_classifier dut(.*);
    reg [7:0] images [0:`NUM_CASES*64-1];
    reg signed [31:0] scores [0:`NUM_CASES*10-1];
    reg [7:0] predictions [0:`NUM_CASES-1];
    integer n, i, cycles, seen;

    initial begin
        $readmemh("images.mem", images);
        $readmemh("scores.mem", scores);
        $readmemh("predictions.mem", predictions);
        repeat(3) @(negedge clk);
        rst=0;
        for (n=0; n<`NUM_CASES; n=n+1) begin
            for (i=0; i<64; i=i+1) begin
                @(negedge clk);
                pixel_we=1;
                pixel_addr=i;
                pixel_data=images[n*64+i];
            end
            @(negedge clk);
            pixel_we=0;
            start=1;
            @(negedge clk);
            start=0;
            if (busy !== 1) $fatal(1, "start not accepted");
            cycles=0;
            seen=0;
            while (done !== 1) begin
                @(negedge clk);
                cycles=cycles+1;
                if (score_valid) begin
                    if (score_class !== seen || score_value !== scores[n*10+seen])
                        $fatal(1, "score mismatch sample=%0d class=%0d got=%0d want=%0d",
                            n, seen, score_value, scores[n*10+seen]);
                    seen=seen+1;
                end
                if (cycles>1400) $fatal(1, "inference timeout");
            end
            if (seen != 10 || prediction !== predictions[n] || busy !== 0)
                $fatal(1, "result mismatch sample=%0d", n);
            @(negedge clk);
            if (done !== 0) $fatal(1, "done is not a one-cycle pulse");
        end
        // Reset must abort an in-flight operation and clear its handshake outputs.
        start=1;
        @(negedge clk); start=0;
        repeat(10) @(negedge clk);
        rst=1;
        @(negedge clk);
        if (busy !== 0 || done !== 0 || score_valid !== 0)
            $fatal(1, "reset failed to abort inference");
        $display("PASS: %0d images, %0d exact integer scores; reset abort checked.",
            `NUM_CASES, `NUM_CASES*10);
        $finish;
    end
    initial begin
        #10000000;
        $fatal(1, "global timeout");
    end
endmodule
