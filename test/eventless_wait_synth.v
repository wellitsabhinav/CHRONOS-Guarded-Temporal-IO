/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
/* Mapping-only wrapper: give the unchanged relative WAIT competitor the same
 * two 8-bit raw-input synchronization banks already inside m3_eventless.
 * Every descriptor input, full GPIO action/output, and existing debug output
 * remains a top-level port. No workload constants specialize either design.
 */
module eventless_wait_synth (
    input wire clk, rst_n,
    input wire [7:0] gpio_in,
    input wire start,
    input wire [23:0] action0, action1, compare_config,
    input wire [3:0] invert_sequence,
    input wire [2:0] response_length,
    input wire [23:0] first_delay, spacing,
    output wire [23:0] gpio_state,
    output wire active, completed, resolved,
    output wire [2:0] bit_index,
    output wire sampled, emitted,
    output wire [7:0] sample_word,
    output wire [23:0] wait_count,
    output wire [1:0] faults,
    output wire [7:0] sync1_state, sync2_state, previous_state
);
    (* ASYNC_REG="TRUE" *) reg [7:0] sync1, sync2;
    always @(posedge clk) begin
        if(!rst_n) begin sync1<=0; sync2<=0; end
        else begin sync1<=gpio_in; sync2<=sync1; end
    end
    assign sync1_state=sync1;
    assign sync2_state=sync2;
    m3_countdown responder (
        .clk(clk), .rst_n(rst_n), .gpio_in(sync2), .start(start),
        .action0(action0), .action1(action1), .compare_config(compare_config),
        .invert_sequence(invert_sequence), .response_length(response_length),
        .first_delay(first_delay), .spacing(spacing), .gpio_state(gpio_state),
        .active(active), .completed(completed), .resolved(resolved), .bit_index(bit_index),
        .sampled(sampled), .emitted(emitted), .sample_word(sample_word),
        .wait_count(wait_count), .faults(faults), .previous_state(previous_state)
    );
endmodule
