`timescale 1ns/1ps
// Standalone DDR bring-up. No neural-network inference or Flash programming.
module acx720_v3_ddr_test_top (
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
    wire sys_clk_i, pll_locked;
    wire sys_rst = reset_n && pll_locked; // MIG config uses active-low reset.
    wire init_calib_complete, tg_compare_error;
    wire monitor_read_activity, monitor_error_sticky;
    clk_wiz_0 u_clock (.clk_in1(clk50m), .resetn(reset_n),
                       .clk_out1(sys_clk_i), .locked(pll_locked));
    example_top u_memory (
        .ddr3_dq(ddr3_dq), .ddr3_dqs_n(ddr3_dqs_n), .ddr3_dqs_p(ddr3_dqs_p),
        .ddr3_addr(ddr3_addr), .ddr3_ba(ddr3_ba), .ddr3_ras_n(ddr3_ras_n),
        .ddr3_cas_n(ddr3_cas_n), .ddr3_we_n(ddr3_we_n), .ddr3_reset_n(ddr3_reset_n),
        .ddr3_ck_p(ddr3_ck_p), .ddr3_ck_n(ddr3_ck_n), .ddr3_cke(ddr3_cke),
        .ddr3_cs_n(ddr3_cs_n), .ddr3_dm(ddr3_dm), .ddr3_odt(ddr3_odt),
        .sys_clk_i(sys_clk_i), .sys_rst(sys_rst),
        .init_calib_complete(init_calib_complete), .tg_compare_error(tg_compare_error),
        .monitor_read_activity(monitor_read_activity), .monitor_error_sticky(monitor_error_sticky)
    );
    assign led0 = monitor_read_activity;
    assign led1 = init_calib_complete;
    assign led2 = monitor_error_sticky;
endmodule
