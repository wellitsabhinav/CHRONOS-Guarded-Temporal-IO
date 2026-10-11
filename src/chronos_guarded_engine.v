/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
// Experimental M1 extension of the M0 FIFO/dispatcher; independent core API.
module chronos_guarded_engine #(
    parameter integer TIME_W=32, GPIO_W=24, DEPTH=8, PRED_W=2, GEN_W=8,
    parameter integer COUNT_W=(DEPTH>1) ? $clog2(DEPTH+1) : 1
) (
    input wire clk, rst_n, event_valid, event_drop,
    output wire event_ready,
    input wire [TIME_W-1:0] event_timestamp,
    input wire [GPIO_W-1:0] event_state, event_state_true,
    input wire event_guarded,
    input wire [PRED_W-1:0] event_predicate,
    input wire [GEN_W-1:0] event_generation,
    input wire predicate_valid, predicate_arm, predicate_value,
    input wire [PRED_W-1:0] predicate_id,
    input wire [GEN_W-1:0] predicate_generation,
    output reg [TIME_W-1:0] time_now,
    output reg [GPIO_W-1:0] gpio_state,
    output reg [COUNT_W-1:0] occupancy,
    output reg [4:0] faults,
    output reg epoch_closed, accepted, rejected, executed,
    output reg normal_executed, false_executed, true_executed, guard_missed,
    output reg predicate_accepted, predicate_rejected,
    output wire [(1<<PRED_W)-1:0] predicate_active_state,
    output wire [(1<<PRED_W)-1:0] predicate_resolved_state, predicate_value_state,
    output wire [(1<<PRED_W)*GEN_W-1:0] predicate_generation_state
);
    localparam integer PTR_W=(DEPTH>1) ? $clog2(DEPTH) : 1;
    localparam integer N_PRED=1<<PRED_W;
    localparam integer ENTRY_W=TIME_W+2*GPIO_W+PRED_W+GEN_W+1;
    localparam [PTR_W-1:0] LAST_PTR=DEPTH-1;
    localparam [COUNT_W-1:0] CAPACITY=DEPTH;
    reg [ENTRY_W-1:0] entries [0:DEPTH-1];
    reg [PTR_W-1:0] read_ptr, write_ptr;
    reg [TIME_W-1:0] last_time;
    reg have_last;
    reg [N_PRED-1:0] p_active, p_resolved, p_value;
    reg [GEN_W-1:0] p_generation [0:N_PRED-1];
    assign predicate_active_state=p_active;
    assign predicate_resolved_state=p_resolved;
    assign predicate_value_state=p_value;
    genvar g;
    generate for(g=0; g<N_PRED; g=g+1) begin: pred_observe
        assign predicate_generation_state[g*GEN_W +: GEN_W]=p_generation[g];
    end endgenerate
    wire [ENTRY_W-1:0] head=entries[read_ptr];
    wire [TIME_W-1:0] head_time;
    wire [GPIO_W-1:0] head_false, head_true;
    wire [PRED_W-1:0] head_pred;
    wire [GEN_W-1:0] head_gen;
    wire head_guarded;
    assign {head_guarded, head_gen, head_pred, head_true, head_false, head_time}=head;
    wire guard_ok=p_active[head_pred] && p_resolved[head_pred] &&
                  p_generation[head_pred]==head_gen;
    wire pop=!epoch_closed && occupancy!=0 && head_time<=time_now;
    wire deadline_bad=epoch_closed || event_timestamp<=time_now;
    wire order_bad=have_last && event_timestamp<=last_time;
    wire consume=event_valid && event_ready;
    wire push=consume && !deadline_bad && !order_bad;
    wire arm_ok=!( &p_generation[predicate_id]) &&
                predicate_generation==(p_generation[predicate_id]+1'b1);
    wire resolve_ok=p_active[predicate_id] && !p_resolved[predicate_id] &&
                    predicate_generation==p_generation[predicate_id];
    wire predicate_ok=!epoch_closed && (predicate_arm ? arm_ok : resolve_ok);
    assign event_ready=rst_n && (occupancy<CAPACITY || pop);
    integer i;
    always @(posedge clk) begin
        if(!rst_n) begin
            time_now<=0; gpio_state<=0; occupancy<=0;
            read_ptr<=0; write_ptr<=0; last_time<=0; have_last<=0;
            faults<=0; epoch_closed<=0; accepted<=0; rejected<=0; executed<=0;
            normal_executed<=0; false_executed<=0; true_executed<=0; guard_missed<=0;
            predicate_accepted<=0; predicate_rejected<=0;
            p_active<=0; p_resolved<=0; p_value<=0;
            for(i=0;i<N_PRED;i=i+1) p_generation[i]<=0;
        end else begin
            time_now<=time_now+1'b1;
            accepted<=push; rejected<=consume && (deadline_bad || order_bad);
            executed<=0; normal_executed<=0; false_executed<=0;
            true_executed<=0; guard_missed<=0;
            predicate_accepted<=predicate_valid && predicate_ok;
            predicate_rejected<=predicate_valid && !predicate_ok;
            if(event_valid && !event_ready && event_drop) faults[0]<=1;
            if(consume && order_bad) faults[1]<=1;
            if(consume && deadline_bad) faults[2]<=1;
            if(pop) begin
                read_ptr<=(read_ptr==LAST_PTR) ? {PTR_W{1'b0}} : read_ptr+1'b1;
                if(head_time!=time_now) faults[2]<=1;
                else if(!head_guarded) begin
                    gpio_state<=head_false; executed<=1; normal_executed<=1;
                end else if(guard_ok) begin
                    gpio_state<=p_value[head_pred] ? head_true : head_false;
                    executed<=1;
                    false_executed<=!p_value[head_pred]; true_executed<=p_value[head_pred];
                end else begin faults[3]<=1; guard_missed<=1; end
            end
            if(push) begin
                entries[write_ptr]<={event_guarded,event_generation,event_predicate,
                                    event_state_true,event_state,event_timestamp};
                write_ptr<=(write_ptr==LAST_PTR) ? {PTR_W{1'b0}} : write_ptr+1'b1;
                last_time<=event_timestamp; have_last<=1;
            end
            case({push,pop})
                2'b10: occupancy<=occupancy+1'b1;
                2'b01: occupancy<=occupancy-1'b1;
                default: begin end
            endcase
            if(predicate_valid) begin
                if(!predicate_ok) faults[4]<=1;
                else if(predicate_arm) begin
                    p_active[predicate_id]<=1; p_generation[predicate_id]<=predicate_generation;
                    p_resolved[predicate_id]<=0; p_value[predicate_id]<=0;
                end else begin
                    p_resolved[predicate_id]<=1; p_value[predicate_id]<=predicate_value;
                end
            end
            if(&time_now) begin
                epoch_closed<=1; occupancy<=0;
                if(occupancy!=0 && !(pop && occupancy==1)) faults[2]<=1;
            end
        end
    end
`ifdef FORMAL
    reg f_past_valid=0;
    (* anyconst *) reg [PTR_W-1:0] f_slot;
    always @(posedge clk) begin
        f_past_valid<=1;
        assume(f_slot<DEPTH);
        if(!f_past_valid) assume(!rst_n);
        if(f_past_valid) begin
            assert(occupancy<=CAPACITY && read_ptr<=LAST_PTR && write_ptr<=LAST_PTR);
            assert(!(false_executed && true_executed));
            assert(executed==(normal_executed || false_executed || true_executed));
            if(!$past(rst_n)) begin
                assert(time_now==0 && occupancy==0 && gpio_state==0 && faults==0);
                assert(p_active==0 && p_resolved==0 && p_value==0);
                assert(!executed && !guard_missed && !accepted && !rejected && !epoch_closed);
                assert(!predicate_accepted && !predicate_rejected);
            end else begin
                if(executed) begin
                    assert($past(pop && head_time==time_now));
                    if(normal_executed) begin
                        assert(!$past(head_guarded));
                        assert(gpio_state==$past(head_false));
                    end else begin
                        assert($past(head_guarded && guard_ok));
                        assert(true_executed==$past(p_value[head_pred]));
                        assert(false_executed!=true_executed);
                        assert(gpio_state==$past(p_value[head_pred] ? head_true : head_false));
                    end
                end
                if($past(pop && head_time==time_now && head_guarded && !guard_ok))
                    assert(guard_missed && faults[3] && !executed && gpio_state==$past(gpio_state));
                if(guard_missed) assert($past(pop && head_time==time_now && head_guarded && !guard_ok));
                if(gpio_state!=$past(gpio_state)) assert(executed);
                if(accepted) begin
                    assert($past(event_timestamp>time_now && !epoch_closed));
                    if($past(have_last)) assert(last_time>$past(last_time));
                end
                if($past(push && write_ptr==f_slot))
                    assert(entries[f_slot]==$past({event_guarded,event_generation,event_predicate,
                                                  event_state_true,event_state,event_timestamp}));
                else assert(entries[f_slot]==$past(entries[f_slot]));
                if($past(pop))
                    assert(read_ptr==(($past(read_ptr)==LAST_PTR) ? 0 : $past(read_ptr)+1'b1));
                else assert(read_ptr==$past(read_ptr));
                for(i=0;i<N_PRED;i=i+1) begin
                    if($past(predicate_valid && predicate_ok && predicate_id==i)) begin
                        if($past(predicate_arm)) begin
                            assert(p_generation[i]==$past(p_generation[i])+1'b1);
                            assert(p_active[i] && !p_resolved[i] && !p_value[i]);
                        end else begin
                            assert(p_resolved[i] && p_value[i]==$past(predicate_value));
                            assert(p_generation[i]==$past(p_generation[i]));
                        end
                    end else begin
                        assert(p_generation[i]==$past(p_generation[i]));
                        assert(p_active[i]==$past(p_active[i]) && p_resolved[i]==$past(p_resolved[i]));
                        assert(p_value[i]==$past(p_value[i]));
                    end
                end
            end
        end
    end
`endif
endmodule
