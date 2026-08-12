; Level 19: Tri-Robot Pipeline Solution
; Robot 0 (starts X=1) sends to Robot 1 (starts X=3), Robot 1 multiplies by 3 & sends to Robot 2 (starts X=5), Robot 2 adds 1 & drops to Outbox

CMP X 5
JEQ r2_stage

CMP X 3
JEQ r1_stage

r0_stage:
    MOVE ; Move to Inbox (0,1)
r0_loop:
    PICK
    SEND INV
    JMP r0_loop

r1_stage:
    RECV R0
    MUL 3 R0
    SEND R0
    JMP r1_stage

r2_stage:
    RECV R0
    ADD 1 R0
    MOV R0 INV
    TURN L
    TURN L
    MOVE ; Move to Outbox (6,1)
    DROP
    TURN L
    TURN L
    MOVE ; Return to (5,1)
    JMP r2_stage
