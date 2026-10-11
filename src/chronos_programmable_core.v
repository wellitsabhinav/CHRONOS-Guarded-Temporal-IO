/* Copyright 2026 CHRONOS contributors. SPDX-License-Identifier: Apache-2.0 */
`default_nettype none
`timescale 1ns/1ps
module chronos_programmable_core #(
    parameter integer TIME_W=32, GPIO_W=24, DEPTH=8, PRED_W=2, GEN_W=8,
    parameter integer GUARDS_ENABLED=1,
    parameter integer COUNT_W=(DEPTH>1) ? $clog2(DEPTH+1) : 1
) (
    input wire clk, rst_n,
    input wire [7:0] gpio_in,
    input wire program_write, program_start,
    input wire [3:0] program_address,
    input wire [31:0] program_data,
    output wire control_ready,
    output reg write_accepted, start_accepted,
    output reg halted, instruction_retired, stalled, sampled,
    output reg [3:0] pc,
    output wire [31:0] instruction,
    output reg [TIME_W-1:0] origin, cursor,
    output wire [TIME_W-1:0] time_now,
    output wire [GPIO_W-1:0] gpio_state,
    output wire [COUNT_W-1:0] occupancy,
    output wire [6:0] faults,
    output wire epoch_closed, accepted, rejected, executed,
    output wire normal_executed, false_executed, true_executed, guard_missed,
    output wire predicate_accepted, predicate_rejected,
    output wire [(1<<PRED_W)-1:0] predicate_active_state, predicate_resolved_state, predicate_value_state,
    output wire [(1<<PRED_W)*GEN_W-1:0] predicate_generation_state,
    output wire [(1<<PRED_W)*COUNT_W-1:0] predicate_refcount_state,
    output reg sampler_busy,
    output reg [7:0] sample_word
);
    localparam integer N_PRED=1<<PRED_W;
    reg [31:0] program_mem [0:15];
    reg [15:0] program_valid;
    reg [GPIO_W-1:0] action0, action1;
    reg [23:0] compare_config;
    reg [6:0] core_faults;
    (* ASYNC_REG="TRUE" *) reg [7:0] sync1, sync2;
    reg [7:0] previous;
    reg [TIME_W-1:0] sample_at, sample_deadline;
    reg [23:0] sample_config;
    reg [PRED_W-1:0] sample_pid;
    reg [GEN_W-1:0] sample_gen;
    reg sample_direct;
    reg [GPIO_W-1:0] sample_action0, sample_action1;
    assign instruction=program_valid[pc] ? program_mem[pc] : 32'b0;
    wire [3:0] opcode=instruction[31:28];
    wire [1:0] instruction_pid=(opcode==4 || opcode==6) ? instruction[1:0] : instruction[25:24];
    wire [PRED_W-1:0] pid=instruction_pid[PRED_W-1:0];
    wire pid_bad=(PRED_W==1) && instruction_pid[1];
    wire [GEN_W-1:0] current_gen=predicate_generation_state[pid*GEN_W +: GEN_W];
    wire [COUNT_W-1:0] current_refs=predicate_refcount_state[pid*COUNT_W +: COUNT_W];
    wire [GEN_W-1:0] next_gen=(&current_gen) ? {{(GEN_W-1){1'b0}},1'b1} : current_gen+1'b1;
    wire [32:0] target_sum={{(33-TIME_W){1'b0}},cursor}+{9'b0,instruction[23:0]};
    wire [32:0] advance_sum={{(33-TIME_W){1'b0}},cursor}+{5'b0,instruction[27:0]};
    wire [32:0] sample_sum={{(33-TIME_W){1'b0}},origin}+{9'b0,instruction[23:0]};
    wire target_overflow=|target_sum[32:TIME_W];
    wire advance_overflow=|advance_sum[32:TIME_W];
    wire sample_overflow=|sample_sum[32:TIME_W];
    wire [TIME_W-1:0] target=target_sum[TIME_W-1:0];
    wire sample_selected=!sample_config[20] || !sync2[sample_config[23:21]];
    wire sample_edge=sync2[sample_config[19:17]] && !previous[sample_config[19:17]];
    wire sample_trigger=sample_config[16] ? sample_edge : time_now==sample_at;
    wire sample_fire=sampler_busy && !epoch_closed && sample_selected && sample_trigger && time_now<=sample_at;
    wire sample_expire=sampler_busy && !epoch_closed && time_now>=sample_at && !sample_fire;
    wire sample_value=(sync2 & sample_config[7:0])==sample_config[15:8];
    wire direct_fire=sample_fire && sample_direct;
    wire [(1<<PRED_W)-1:0] predicate_hold=sampler_busy ? ({{(N_PRED-1){1'b0}},1'b1} << sample_pid) : 0;
    assign control_ready=rst_n && halted && occupancy==0 && !sampler_busy && !epoch_closed;
    wire [4:0] engine_faults;
    assign faults=core_faults | {2'b0,engine_faults};
    reg event_valid, event_guarded, predicate_valid, predicate_arm, predicate_value;
    wire event_ready;
    wire event_legal, predicate_legal, have_last;
    wire [TIME_W-1:0] last_timestamp;
    reg [TIME_W-1:0] event_timestamp;
    reg [GPIO_W-1:0] event_state, event_state_true;
    reg [PRED_W-1:0] event_predicate, predicate_id;
    reg [GEN_W-1:0] event_generation, predicate_generation;
    reg do_retire, do_stall, do_fault, do_halt, do_sample;
    reg [4:0] instruction_fault;
    reg [27:0] allowed;
    always @* begin
        case(opcode)
            0: allowed=0;
            1,2: allowed=28'h1ffffff;
            3,5,8: allowed=28'h7ffffff;
            4: allowed=3;
            6: allowed=7;
            7: allowed=28'h0ffffff;
            9: allowed=28'hfffffff;
            default: allowed=0;
        endcase
        event_valid=direct_fire;
        event_guarded=0; event_timestamp=sample_deadline;
        event_state=sample_value ? sample_action1 : sample_action0;
        event_state_true=0; event_predicate=0; event_generation=0;
        predicate_valid=sample_fire; predicate_arm=0; predicate_value=sample_value;
        predicate_id=sample_pid; predicate_generation=sample_gen;
        do_retire=0; do_stall=0; do_fault=0; do_halt=0; do_sample=0; instruction_fault=0;
        if(!halted && !program_write && !program_start) begin
            if(!program_valid[pc] || opcode>9 || (instruction[27:0] & ~allowed)!=0 || epoch_closed)
                do_fault=1;
            else case(opcode)
                0: begin do_retire=1; do_halt=1; end
                1,7: do_retire=1;
                9: begin do_retire=!advance_overflow; do_fault=advance_overflow; end
                4,6: begin
                    if(pid_bad) do_fault=1;
                    else if(sample_fire) do_stall=1;
                    else if(opcode==4 && (current_refs!=0 || predicate_hold[pid])) do_stall=1;
                    else if(opcode==6 && (!predicate_active_state[pid] || predicate_resolved_state[pid])) do_fault=1;
                    else begin
                        predicate_valid=1; predicate_arm=opcode==4;
                        predicate_id=pid; predicate_generation=opcode==4 ? next_gen : current_gen;
                        predicate_value=instruction[2]; do_retire=1;
                    end
                end
                5: begin
                    if(pid_bad || !predicate_active_state[pid] || predicate_resolved_state[pid] ||
                       sample_overflow || sample_sum[TIME_W-1:0]<=time_now) do_fault=1;
                    else if(sampler_busy) do_stall=1;
                    else begin do_sample=1; do_retire=1; end
                end
                2,3,8: begin
                    if(target_overflow || target<=time_now) begin do_fault=1; instruction_fault[2]=1; end
                    else if(have_last && target<=last_timestamp) begin do_fault=1; instruction_fault[1]=1; end
                    else if((opcode==3 || opcode==8) && (pid_bad || !predicate_active_state[pid] ||
                            (opcode==3 && GUARDS_ENABLED==0))) begin do_fault=1; instruction_fault[4]=1; end
                    else if(direct_fire || !event_ready || (opcode==8 && !predicate_resolved_state[pid])) do_stall=1;
                    else begin
                        event_valid=1; event_timestamp=target; event_guarded=opcode==3;
                        event_predicate=pid; event_generation=current_gen;
                        if(opcode==2) event_state=instruction[24] ? action1 : action0;
                        else begin
                            event_state=(instruction[26] ^ (opcode==8 && predicate_value_state[pid])) ? action1 : action0;
                            event_state_true=instruction[26] ? action0 : action1;
                        end
                        do_retire=1;
                    end
                end
                default: do_fault=1;
            endcase
        end
    end
    chronos_reclaiming_engine #(.TIME_W(TIME_W),.GPIO_W(GPIO_W),.DEPTH(DEPTH),
        .PRED_W(PRED_W),.GEN_W(GEN_W),.GUARDS_ENABLED(GUARDS_ENABLED)) engine (
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_drop(direct_fire),.event_ready(event_ready),
        .event_legal(event_legal),.predicate_legal(predicate_legal),.last_timestamp(last_timestamp),.have_last_state(have_last),
        .event_timestamp(event_timestamp),.event_state(event_state),.event_state_true(event_state_true),
        .event_guarded(event_guarded),.event_predicate(event_predicate),.event_generation(event_generation),
        .predicate_valid(predicate_valid),.predicate_arm(predicate_arm),.predicate_value(predicate_value),
        .predicate_id(predicate_id),.predicate_generation(predicate_generation),.predicate_hold(predicate_hold),
        .time_now(time_now),.gpio_state(gpio_state),.occupancy(occupancy),.faults(engine_faults),
        .epoch_closed(epoch_closed),.accepted(accepted),.rejected(rejected),.executed(executed),
        .normal_executed(normal_executed),.false_executed(false_executed),.true_executed(true_executed),
        .guard_missed(guard_missed),.predicate_accepted(predicate_accepted),.predicate_rejected(predicate_rejected),
        .predicate_active_state(predicate_active_state),.predicate_resolved_state(predicate_resolved_state),
        .predicate_value_state(predicate_value_state),.predicate_generation_state(predicate_generation_state),
        .predicate_refcount_state(predicate_refcount_state)
    );
    wire control_bad=(program_write || program_start) && (!control_ready || (program_write && program_start));
    wire program_error=control_bad || do_fault || (do_retire && !do_halt && pc==15);
    wire sampler_error=sample_expire || (direct_fire && (!event_ready || !event_legal)) || (sample_fire && !predicate_legal);
    always @(posedge clk) begin
        if(!rst_n) begin
            program_valid<=0; pc<=0; origin<=0; cursor<=0;
            action0<=0; action1<=0; compare_config<=0; core_faults<=0;
            halted<=1; instruction_retired<=0; stalled<=0; sampled<=0;
            write_accepted<=0; start_accepted<=0; sampler_busy<=0;
            sync1<=0; sync2<=0; previous<=0; sample_word<=0;
            sample_at<=0; sample_deadline<=0; sample_config<=0; sample_pid<=0; sample_gen<=0;
            sample_direct<=0; sample_action0<=0; sample_action1<=0;
        end else begin
            sync1<=gpio_in; sync2<=sync1; previous<=sync2;
            instruction_retired<=do_retire; stalled<=do_stall; sampled<=sample_fire;
            write_accepted<=0; start_accepted<=0;
            core_faults<=core_faults | {sampler_error,program_error,instruction_fault};
            if(sample_fire || sample_expire) sampler_busy<=0;
            if(sample_fire) sample_word<=sync2;
            if(program_write || program_start) begin
                if(control_bad) halted<=1;
                else if(program_write) begin
                    program_mem[program_address]<=program_data;
                    program_valid[program_address]<=1; write_accepted<=1;
                end else begin
                    pc<=0; origin<=time_now; cursor<=time_now; action0<=0; action1<=0; compare_config<=0;
                    halted<=0; start_accepted<=1;
                end
            end else if(!halted) begin
                if(do_fault) halted<=1;
                else if(do_retire) begin
                    if(do_halt) halted<=1;
                    else if(pc==15) halted<=1;
                    else pc<=pc+1'b1;
                    if(opcode==1) begin
                        if(instruction[24]) action1<=instruction[GPIO_W-1:0];
                        else action0<=instruction[GPIO_W-1:0];
                    end
                    if(opcode==7) compare_config<=instruction[23:0];
                    if(opcode==9) cursor<=advance_sum[TIME_W-1:0];
                    if(opcode==2 || opcode==3 || opcode==8) cursor<=target;
                    if(do_sample) begin
                        sampler_busy<=1; sample_at<=sample_sum[TIME_W-1:0]; sample_config<=compare_config;
                        sample_pid<=pid; sample_gen<=current_gen; sample_direct<=instruction[26];
                        sample_deadline<=cursor; sample_action0<=action0; sample_action1<=action1;
                    end
                end
            end
            if(&time_now || epoch_closed) begin sampler_busy<=0; halted<=1; end
        end
    end
`ifdef FORMAL
    reg f_past_valid=0;
    always @(posedge clk) begin
        f_past_valid<=1;
        if(!f_past_valid) assume(!rst_n);
        if(f_past_valid && $past(rst_n)) begin
            if(sampled) assert($past(sample_fire));
            if($past(sampler_busy && !sample_fire && !sample_expire && !(&time_now) && !epoch_closed)) begin
                assert(sampler_busy);
                assert(sample_pid==$past(sample_pid) && sample_gen==$past(sample_gen));
            end
            if(predicate_accepted && $past(predicate_arm))
                assert(!$past(sampler_busy && sample_pid==predicate_id));
            if($past(sample_fire)) begin
                assert(sample_word==$past(sync2));
                assert(!sampler_busy);
            end
        end
    end
`endif
endmodule
