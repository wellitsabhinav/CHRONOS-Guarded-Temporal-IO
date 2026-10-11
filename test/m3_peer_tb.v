/* Test-only comparison fixture. Production M2 source is unchanged. */
`timescale 1ns/1ps
module m3_peer_tb;
    reg clk, rst_n, ena;
    reg [7:0] ui_in, uio_in;
    wire [7:0] uo_out, uio_out, uio_oe;
    reg baseline_start;
    reg [2:0] baseline_length;
    reg baseline_trigger_rising;
    reg [23:0] wait_first_delay, wait_spacing;
    wire [23:0] wait_gpio, wait_count;
    wire wait_active, wait_completed, wait_resolved, wait_sampled, wait_emitted;
    wire [2:0] wait_index;
    wire [1:0] wait_faults;
    wire [7:0] wait_sample_word, wait_previous;
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
        .response_length(baseline_length), .emit_pin(3'd2), .emit_rising(!baseline_trigger_rising),
        .trigger_rising(baseline_trigger_rising), .hold_first_emit(1'b1),
        .gpio_state(baseline_gpio), .armed(baseline_armed), .active(baseline_active),
        .completed(baseline_completed), .bit_index(baseline_index),
        .sampled(baseline_sampled), .emitted(baseline_emitted), .cancelled(baseline_cancelled),
        .sample_word(baseline_sample_word), .sync1_state(baseline_sync1),
        .sync2_state(baseline_sync2), .previous_state(baseline_previous));
    m3_countdown wait_baseline(.clk(clk), .rst_n(rst_n), .gpio_in(baseline_sync2),
        .start(baseline_start), .action0(24'h010000), .action1(24'h010100),
        .compare_config(24'h750202), .invert_sequence(4'b0110),
        .response_length(baseline_length), .first_delay(wait_first_delay), .spacing(wait_spacing),
        .gpio_state(wait_gpio), .active(wait_active), .completed(wait_completed),
        .resolved(wait_resolved), .bit_index(wait_index), .sampled(wait_sampled), .emitted(wait_emitted),
        .sample_word(wait_sample_word), .wait_count(wait_count), .faults(wait_faults),
        .previous_state(wait_previous));
endmodule
