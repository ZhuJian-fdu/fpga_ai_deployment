`timescale 1ns/1ps
// Fixed AXI contract: 128-bit data, 28-bit BYTE address, ID=0, INCR,
// 16 beats per burst (LEN=15, SIZE=4), all strobes asserted.
// Write the ENTIRE range before reading: an aliased high address must not
// overwrite a location immediately before its own comparison hides the fault.
module ddr_full_sweep #(
    parameter [27:0] START_ADDR = 28'h0000000,
    parameter [27:0] LAST_BURST = 28'hfffff00,
    parameter integer TIMEOUT_BITS = 27
)(
    input wire clk, reset, calibrated,
    output wire [27:0] awaddr, output wire awvalid, input wire awready,
    output wire [127:0] wdata, output wire wlast, wvalid, input wire wready,
    input wire [3:0] bid, input wire [1:0] bresp, input wire bvalid,
    output wire bready,
    output wire [27:0] araddr, output wire arvalid, input wire arready,
    input wire [127:0] rdata, input wire [3:0] rid,
    input wire [1:0] rresp, input wire rlast, rvalid, output wire rready,
    output reg done, failed,
    output reg [3:0] error_code,
    output reg [27:0] error_addr,
    output reg [25:0] checked_beats,
    output reg [31:0] elapsed_cycles
);
    localparam WAIT_CAL=0, AW_W=1, B=3, AR=4, R=5, PASS=6, FAIL=7;
    reg [2:0] state;
    reg [27:0] base;
    reg [3:0] beat;
    reg inverse;
    reg aw_sent, w_sent;
    reg [TIMEOUT_BITS-1:0] watchdog;
    wire [27:0] beat_addr = base + {20'b0, beat, 4'b0};
    wire progress = (awvalid && awready) || (wvalid && wready) ||
                    (bready && bvalid) || (arvalid && arready) ||
                    (rready && rvalid);
    function [127:0] pattern;
        input [27:0] addr;
        input inv;
        reg [31:0] a;
        begin
            a = {4'b0, addr};
            pattern = {a ^ 32'hc3c35a5a, a ^ 32'h96966969,
                       a ^ 32'h5a5aa5a5, a ^ 32'h12345678} ^ {128{inv}};
        end
    endfunction
    assign awaddr=base;
    assign araddr=base;
    assign awvalid=(state==AW_W) && !aw_sent;
    assign wvalid=(state==AW_W) && !w_sent;
    assign wdata=pattern(beat_addr,inverse);
    assign wlast=(beat==15);
    assign bready=(state==B);
    assign arvalid=(state==AR);
    assign rready=(state==R);

    always @(posedge clk) begin
        if (reset) begin
            state<=WAIT_CAL; base<=START_ADDR; beat<=0; inverse<=0;
            aw_sent<=0; w_sent<=0;
            done<=0; failed<=0; error_code<=0; error_addr<=0;
            checked_beats<=0; elapsed_cycles<=0; watchdog<=0;
        end else if (state!=PASS && state!=FAIL) begin
            if (state!=WAIT_CAL) elapsed_cycles<=elapsed_cycles+1'b1;
            if (progress || state==WAIT_CAL) watchdog<=0;
            else watchdog<=watchdog+1'b1;
            // Latch timeout without withdrawing VALID from a stalled channel.
            // If the slave recovers, drain the outstanding transaction, then stop.
            if (!failed && state!=WAIT_CAL && (&watchdog) && !progress) begin
                failed<=1; error_code<=5; error_addr<=beat_addr;
            end else case (state)
                WAIT_CAL: if (calibrated) state<=AW_W;
                AW_W: begin
                    // Address and data channels advance independently; neither
                    // VALID waits for the other channel's READY.
                    if (awvalid && awready) aw_sent<=1;
                    if (wvalid && wready) begin
                        if (beat==15) w_sent<=1;
                        else beat<=beat+1'b1;
                    end
                    if ((aw_sent || awready) && (w_sent || (wready && beat==15))) state<=B;
                end
                B: if (bvalid) begin
                    if (failed) state<=FAIL;
                    else if (bresp!=0 || bid!=0) begin
                        state<=FAIL; failed<=1; error_code<=1; error_addr<=base;
                    end else if (base==LAST_BURST) begin
                        base<=START_ADDR; beat<=0; state<=AR;
                    end else begin
                        base<=base+28'd256; beat<=0; aw_sent<=0; w_sent<=0; state<=AW_W;
                    end
                end
                AR: if (arready) begin beat<=0; state<=R; end
                R: if (rvalid) begin
                    if (failed) begin
                        if (rlast) state<=FAIL;
                    end else if (rresp!=0 || rid!=0 || rlast!=(beat==15) ||
                        rdata!=pattern(beat_addr,inverse)) begin
                        state<=FAIL; failed<=1; error_addr<=beat_addr;
                        if (rresp!=0 || rid!=0) error_code<=2;
                        else if (rlast!=(beat==15)) error_code<=3;
                        else error_code<=4;
                    end else begin
                        checked_beats<=checked_beats+1'b1;
                        if (beat==15) begin
                            if (base==LAST_BURST) begin
                                if (inverse) begin done<=1; state<=PASS; end
                                else begin
                                    inverse<=1; base<=START_ADDR; beat<=0;
                                    aw_sent<=0; w_sent<=0; state<=AW_W;
                                end
                            end else begin base<=base+28'd256; state<=AR; end
                        end else beat<=beat+1'b1;
                    end
                end
                default: begin state<=FAIL; failed<=1; error_code<=6; end
            endcase
        end
    end
endmodule
