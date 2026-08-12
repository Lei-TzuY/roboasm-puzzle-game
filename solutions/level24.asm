; Level 24: Quad-Robot Distributed Parallel Sum Solution
; Robot 0 (X=1), Robot 1 (X=3), Robot 2 (X=5), Robot 3 (X=7)

CMP X 7
JEQ r3_stage

CMP X 5
JEQ r2_stage

CMP X 3
JEQ r1_stage

r0_stage:
    MOVE ; Move to Inbox (0,1)
    PICK
    SEND INV ; Send 10
    PICK
    SEND INV ; Send 20
    PICK
    SEND INV ; Send 30
    PICK
    SEND INV ; Send 40
    HLT

r1_stage:
    RECV R0
    RECV R1
    ADD R0 R1
    SEND R1
    HLT

r2_stage:
    RECV R0
    RECV R1
    ADD R0 R1
    SEND R1
    HLT

r3_stage:
    RECV R0
    RECV R1
    ADD R0 R1
    MOV R1 INV
    TURN L
    TURN L
    MOVE ; Move to Outbox (8,1)
    DROP
    HLT
