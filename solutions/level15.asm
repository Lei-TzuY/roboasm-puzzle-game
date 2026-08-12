; Level 15: Dual Robot Messaging Solution
; Robot 0 (at 1,1) moves to Inbox (0,1) and SENDS items.
; Robot 1 (at 5,1) RECVs items, doubles them, and DROPs at Outbox (6,1).

CMP X 5
JEQ receiver

sender:
    MOVE ; Move to Inbox (0,1)
sender_loop:
    PICK
    SEND INV
    JMP sender_loop

receiver:
    RECV R0
    ADD R0 R0
    MOV R0 INV
    TURN L
    TURN L
    MOVE ; Move to Outbox (6,1)
    DROP
    TURN L
    TURN L
    MOVE ; Return to (5,1)
    JMP receiver
