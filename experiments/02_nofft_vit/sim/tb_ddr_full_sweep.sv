`timescale 1ns/1ps
// Behavioral AXI memory with independent stalls, coverage checks and faults.
// This tests our master; it is not a MIG/DDR PHY simulation.
module tb_ddr_full_sweep;
    parameter CASE=0;
    localparam [27:0] FIRST=(CASE==9) ? 28'hffffe00 : 0;
    localparam [27:0] LAST=(CASE==9) ? 28'hfffff00 : 28'h0001f00;
    localparam integer WORDS=(LAST-FIRST+256)/16;
    reg clk=0, reset=1, calibrated=0;
    always #5 clk=~clk;
    wire [27:0] awaddr, araddr;
    wire awvalid,awready,wvalid,wready,wlast,bready,arvalid,arready,rready;
    wire [127:0] wdata;
    reg [127:0] rdata=0;
    reg [3:0] bid=0,rid=0;
    reg [1:0] bresp=0,rresp=0;
    reg bvalid=0,rvalid=0,rlast=0;
    wire done,failed;
    wire [3:0] error_code;
    wire [27:0] error_addr;
    wire [25:0] checked_beats;
    wire [31:0] elapsed_cycles;
    ddr_full_sweep #(.START_ADDR(FIRST),.LAST_BURST(LAST),.TIMEOUT_BITS(8)) dut(.*);
    reg [127:0] mem[0:511];
    reg writing=0, reading=0, bpending=0;
    reg [27:0] wa=0,ra=0;
    integer wb=0,rb=0,cycles=0,nw=0,nr=0,na=0;
    reg [15:0] rng=16'h93a7;
    assign awready=!reset && !writing && !bpending && !bvalid && rng[0] && CASE!=6 &&
                   (CASE!=12 || cycles>290) && (CASE!=14 || wvalid) &&
                   (CASE!=15 || wb>=4);
    assign wready=(writing || (CASE==15 && awvalid)) && !bpending && !bvalid && rng[2];
    assign arready=!reset && !reading && !rvalid && rng[4];
    function integer idx(input [27:0] a);
        idx=((a-FIRST)>>4) % ((CASE==2) ? WORDS/2 : WORDS);
    endfunction
    function [127:0] expected(input [27:0] a,input inv);
        expected[31:0]={4'b0,a}^32'h12345678;
        expected[63:32]={4'b0,a}^32'h5a5aa5a5;
        expected[95:64]={4'b0,a}^32'h96966969;
        expected[127:96]={4'b0,a}^32'hc3c35a5a;
        if(inv) expected=~expected;
    endfunction
    reg stalled_aw=0,stalled_w=0,stalled_ar=0;
    reg [27:0] oldaw,oldar;
    reg [128:0] oldw;
    always @(posedge clk) begin
        if (reset) begin
            writing<=0; reading<=0; bpending<=0; bvalid<=0; rvalid<=0;
            nw<=0;nr<=0;na<=0;wb<=0;rb<=0;
            stalled_aw<=0;stalled_w<=0;stalled_ar<=0;
        end else begin
            cycles<=cycles+1;
            rng<={rng[14:0],rng[15]^rng[13]^rng[12]^rng[10]};
            if(cycles>100000) $fatal(1,"Testbench deadline CASE=%0d",CASE);
            if(stalled_aw && (!awvalid || awaddr!==oldaw)) $fatal(1,"AW changed while stalled");
            if(stalled_w && (!wvalid || {wlast,wdata}!==oldw)) $fatal(1,"W changed while stalled");
            if(stalled_ar && (!arvalid || araddr!==oldar)) $fatal(1,"AR changed while stalled");
            // A timeout must not withdraw a stalled VALID, even after failure latches.
            stalled_aw<=awvalid&&!awready;
            stalled_w<=wvalid&&!wready;
            stalled_ar<=arvalid&&!arready;
            oldaw<=awaddr; oldw<={wlast,wdata}; oldar<=araddr;
            if(awvalid&&awready) begin
                if(awaddr!==FIRST+(na%(WORDS/16))*256 || awaddr[7:0]!=0) $fatal(1,"AW coverage/order");
                if(nw>=WORDS && nr<WORDS) $fatal(1,"Second write before full read");
                writing<=1;wa<=awaddr;na<=na+1;
            end
            if(wvalid&&wready) begin
                if(wlast!==(wb==15)) $fatal(1,"WLAST");
                if(wdata!==expected(FIRST+(nw%WORDS)*16,nw>=WORDS)) $fatal(1,"Write pattern");
                mem[idx(FIRST+(nw%WORDS)*16)]<=wdata;nw<=nw+1;
                if(wb==15) begin writing<=0;bpending<=1; end
                else wb<=wb+1;
            end
            if(bpending && rng[3] && CASE!=10) begin
                bvalid<=1;bpending<=0;bresp<=(CASE==3)?2:0;bid<=(CASE==7)?1:0;
            end
            if(bvalid&&bready) begin bvalid<=0;wb<=0; end
            if(arvalid&&arready) begin
                if(nw<WORDS*((nr/WORDS)+1)) $fatal(1,"Read before entire write");
                if(araddr!==FIRST+(nr%WORDS)*16 || araddr[7:0]!=0) $fatal(1,"AR coverage/order");
                reading<=1;ra<=araddr;rb<=0;
            end
            if(reading && !rvalid && rng[5] && (CASE!=13 || failed)) begin
                rvalid<=1;rdata<=mem[idx(ra+rb*16)] ^ ((CASE==1 && rb==7)?128'b1:128'b0);
                rresp<=(CASE==4)?2:0;rid<=0;
                rlast<=(CASE==5)?(rb==3):((CASE==11)?1'b0:(rb==15));
            end
            if(rvalid&&rready) begin
                rvalid<=0;nr<=nr+1;
                if(rb==15) reading<=0;else rb<=rb+1;
            end
        end
    end
    initial begin
        repeat(4) @(negedge clk);reset=0;
        repeat(10) @(negedge clk);
        if(awvalid||arvalid) $fatal(1,"Traffic before calibration");
        calibrated=1;
        if(CASE==8) begin
            wait(nw>48); @(negedge clk);reset=1;calibrated=0;
            repeat(4) @(negedge clk);reset=0;
            repeat(6) @(negedge clk);calibrated=1;
        end
        wait(done||failed);
        @(negedge clk);
        if(CASE==0 || CASE==8 || CASE==9 || CASE==14 || CASE==15) begin
            if(!done || failed || checked_beats!=2*WORDS || nw!=2*WORDS || nr!=2*WORDS)
                $fatal(1,"Completion/coverage CASE=%0d writes=%0d reads=%0d checked=%0d",CASE,nw,nr,checked_beats);
        end else begin
            if(!failed || done) $fatal(1,"Fault missed CASE=%0d",CASE);
            case(CASE)
                1,2: if(error_code!=4) $fatal(1,"Data fault code");
                3,7: if(error_code!=1) $fatal(1,"B fault code");
                4: if(error_code!=2) $fatal(1,"R response fault code");
                5,11: if(error_code!=3) $fatal(1,"RLAST fault code");
                6,10,12,13: if(error_code!=5) $fatal(1,"Timeout fault code");
            endcase
        end
        if(CASE==12 || CASE==13) begin
            wait(dut.state==7);
            if(!failed || done || error_code!=5) $fatal(1,"Timeout latch after drain");
        end
        // Done/error latch until reset; no new requests after termination.
        repeat(8) @(negedge clk);
        if(CASE!=6 && CASE!=10 && (awvalid||wvalid||arvalid)) $fatal(1,"Traffic after termination");
        $display("PASS CASE=%0d done=%0d failed=%0d code=%0d checked=%0d cycles=%0d",CASE,done,failed,error_code,checked_beats,elapsed_cycles);
        $finish;
    end
endmodule
