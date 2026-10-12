/* Test-only wiring: unchanged M3 comparators; public actions remain unmasked. */
`default_nettype none
`timescale 1ns/1ps
module eventless_gate_tb;
    reg clk, rst_n, start;
    reg [7:0] gpio_in;
    reg [23:0] first_delay;
    wire [23:0] e_gpio, w_gpio;
    wire e_armed,e_active,e_completed,e_sampled,e_emitted,e_cancelled;
    wire w_active,w_completed,w_resolved,w_sampled,w_emitted;
    wire [2:0] e_bit_index,w_bit_index;
    wire [7:0] e_sample_word,w_sample_word,sync1,sync2,previous,w_previous;
    wire [23:0] w_count;
    wire [1:0] w_faults;
    m3_eventless edge_reactive(
        .clk(clk),.rst_n(rst_n),.start(start),.gpio_in(gpio_in),
        .action0(24'h010000),.action1(24'h010100),.compare_config(24'h750202),
        .invert_sequence(4'b0110),.response_length(3'd4),
        .trigger_rising(1'b1),.emit_pin(3'd2),.emit_rising(1'b0),.hold_first_emit(1'b1),
        .gpio_state(e_gpio),.armed(e_armed),.active(e_active),.completed(e_completed),
        .sampled(e_sampled),.emitted(e_emitted),.cancelled(e_cancelled),
        .bit_index(e_bit_index),.sample_word(e_sample_word),
        .sync1_state(sync1),.sync2_state(sync2),.previous_state(previous));
    m3_countdown relative_wait(
        .clk(clk),.rst_n(rst_n),.start(start),.gpio_in(sync2),
        .action0(24'h010000),.action1(24'h010100),.compare_config(24'h750202),
        .invert_sequence(4'b0110),.response_length(3'd4),
        .first_delay(first_delay),.spacing(24'd8),.gpio_state(w_gpio),
        .active(w_active),.completed(w_completed),.resolved(w_resolved),
        .sampled(w_sampled),.emitted(w_emitted),.bit_index(w_bit_index),
        .sample_word(w_sample_word),.wait_count(w_count),.faults(w_faults),
        .previous_state(w_previous));
endmodule
