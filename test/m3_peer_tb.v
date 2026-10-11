/* Test-only comparison fixture. Production M2 source is unchanged. */
`timescale 1ns/1ps
module m3_peer_tb;
    reg clk, rst_n, ena;
    reg [7:0] ui_in, uio_in;
    wire [7:0] uo_out, uio_out, uio_oe;
    reg baseline_start;
    reg [2:0] baseline_length;
    wire [23:0] baseline_gpio;
    wire baseline_armed, baseline_active, baseline_completed;
    wire [2:0] baseline_index;
    wire baseline_sampled, baseline_emitted, baseline_cancelled;
    wire [7:0] baseline_sample_word, baseline_sync1, baseline_sync2, baseline_previous;
    tt_um_chronos_m2 chronos(.clk(clk), .rst_n(rst_n), .ena(ena),
        .ui_in(ui_in), .uio_in(uio_in), .uo_out(uo_out),
        .uio_out(uio_out), .uio_oe(uio_oe));
    m3_eventless baseline(.clk(clk), .rst_n(rst_n), .gpio_in(uio_in),
        .start(baseline_start), .action0(24'h010000), .action1(24'h010100),
        .compare_config(24'h750202), .invert_sequence(4'b0110),
        .response_length(baseline_length), .emit_pin(3'd2), .emit_rising(1'b0),
        .trigger_rising(1'b1), .hold_first_emit(1'b1),
        .gpio_state(baseline_gpio), .armed(baseline_armed), .active(baseline_active),
        .completed(baseline_completed), .bit_index(baseline_index),
        .sampled(baseline_sampled), .emitted(baseline_emitted), .cancelled(baseline_cancelled),
        .sample_word(baseline_sample_word), .sync1_state(baseline_sync1),
        .sync2_state(baseline_sync2), .previous_state(baseline_previous));
endmodule
