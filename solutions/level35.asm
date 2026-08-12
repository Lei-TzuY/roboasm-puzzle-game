; Level 35: The AI Assembly Synthesis Grand Finale Solution
; Robot 0 (X=1), Robot 1 (X=5)

CMP X 5
JEQ r1_stage

r0_stage:
    MOVE ; Move to Inbox (0,1)
r0_loop:
    PICK
    MUL 2 INV
    SEND INV
    JMP r0_loop

r1_stage:
    RECV R0
    ADD 5 R0
    MOV R0 INV
    TURN L
    TURN L
    MOVE ; Move to Outbox (6,1)
    DROP
    TURN L
    TURN L
    MOVE ; Return to (5,1)
    JMP r1_stage
