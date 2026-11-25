`timescale 1ns/1ps
// Standalone DDR bring-up. No neural-network inference or Flash programming.
module acx720_v3_ddr_full_top (
    input wire clk50m, input wire reset_n,
    output wire led0, output wire led1, output wire led2,
    inout wire [15:0] ddr3_dq,
    inout wire [1:0] ddr3_dqs_n, ddr3_dqs_p,
    output wire [13:0] ddr3_addr,
    output wire [2:0] ddr3_ba,
    output wire ddr3_ras_n, ddr3_cas_n, ddr3_we_n, ddr3_reset_n,
    output wire [0:0] ddr3_ck_p, ddr3_ck_n, ddr3_cke, ddr3_cs_n, ddr3_odt,
    output wire [1:0] ddr3_dm
);
    wire sys_clk_i, pll_locked, clk, rst, calibrated;
    reg aresetn;
    always @(posedge clk) aresetn <= ~rst;
    wire sys_rst = reset_n && pll_locked;
    wire [27:0] awaddr, araddr;
    wire awvalid, awready, wlast, wvalid, wready, bvalid, bready;
    wire arvalid, arready, rlast, rvalid, rready;
    wire [127:0] wdata, rdata;
    wire [3:0] bid, rid;
    wire [1:0] bresp, rresp;
    wire done, failed;
    reg [25:0] heartbeat;
    always @(posedge clk) begin
        if (rst || !aresetn) heartbeat <= 0;
        else if (calibrated && !done && !failed) heartbeat <= heartbeat + 1'b1;
    end
    assign led0 = failed ? 1'b0 : (done ? 1'b1 : heartbeat[25]);
    assign led1 = calibrated;
    assign led2 = failed;
    clk_wiz_0 u_clock (.clk_in1(clk50m), .resetn(reset_n),
                       .clk_out1(sys_clk_i), .locked(pll_locked));
    ddr_full_sweep u_test (
        .clk(clk), .reset(rst || !aresetn), .calibrated(calibrated),
        .awaddr(awaddr), .awvalid(awvalid), .awready(awready),
        .wdata(wdata), .wlast(wlast), .wvalid(wvalid), .wready(wready),
        .bid(bid), .bresp(bresp), .bvalid(bvalid), .bready(bready),
        .araddr(araddr), .arvalid(arvalid), .arready(arready),
        .rdata(rdata), .rid(rid), .rresp(rresp), .rlast(rlast),
        .rvalid(rvalid), .rready(rready), .done(done), .failed(failed),
        .error_code(), .error_addr(), .checked_beats(), .elapsed_cycles()
    );
    mig_7series_0 u_memory (
        .ddr3_dq(ddr3_dq),
        .ddr3_dqs_n(ddr3_dqs_n),
        .ddr3_dqs_p(ddr3_dqs_p),
        .ddr3_addr(ddr3_addr),
        .ddr3_ba(ddr3_ba),
        .ddr3_ras_n(ddr3_ras_n),
        .ddr3_cas_n(ddr3_cas_n),
        .ddr3_we_n(ddr3_we_n),
        .ddr3_reset_n(ddr3_reset_n),
        .ddr3_ck_p(ddr3_ck_p),
        .ddr3_ck_n(ddr3_ck_n),
        .ddr3_cke(ddr3_cke),
        .ddr3_cs_n(ddr3_cs_n),
        .ddr3_dm(ddr3_dm),
        .ddr3_odt(ddr3_odt),
        .sys_clk_i(sys_clk_i),
        .sys_rst(sys_rst),
        .aresetn(aresetn),
        .ui_clk(clk),
        .ui_clk_sync_rst(rst),
        .mmcm_locked(),
        .init_calib_complete(calibrated),
        .device_temp(),
        .app_sr_req(1'b0),
        .app_ref_req(1'b0),
        .app_zq_req(1'b0),
        .app_sr_active(),
        .app_ref_ack(),
        .app_zq_ack(),
        .s_axi_awid(4'b0),
        .s_axi_awaddr(awaddr),
        .s_axi_awlen(8'd15),
        .s_axi_awsize(3'd4),
        .s_axi_awburst(2'b01),
        .s_axi_awlock(1'b0),
        .s_axi_awcache(4'b0011),
        .s_axi_awprot(3'b0),
        .s_axi_awqos(4'b0),
        .s_axi_awvalid(awvalid),
        .s_axi_awready(awready),
        .s_axi_arid(4'b0),
        .s_axi_araddr(araddr),
        .s_axi_arlen(8'd15),
        .s_axi_arsize(3'd4),
        .s_axi_arburst(2'b01),
        .s_axi_arlock(1'b0),
        .s_axi_arcache(4'b0011),
        .s_axi_arprot(3'b0),
        .s_axi_arqos(4'b0),
        .s_axi_arvalid(arvalid),
        .s_axi_arready(arready),
        .s_axi_wdata(wdata),
        .s_axi_wlast(wlast),
        .s_axi_wvalid(wvalid),
        .s_axi_wready(wready),
        .s_axi_bid(bid),
        .s_axi_bresp(bresp),
        .s_axi_bvalid(bvalid),
        .s_axi_bready(bready),
        .s_axi_rid(rid),
        .s_axi_rdata(rdata),
        .s_axi_rresp(rresp),
        .s_axi_rlast(rlast),
        .s_axi_rvalid(rvalid),
        .s_axi_rready(rready),
        .s_axi_wstrb(16'hffff)
    );
endmodule
