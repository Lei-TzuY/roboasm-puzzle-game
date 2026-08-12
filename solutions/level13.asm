; Level 13: Stack Reverser Solution
; Read 4 numbers into stack at Inbox (0,1), then move to Outbox (4,1) and pop in reverse order

#define COUNT 4

; Move to Inbox at (0,1)
MOVE
MOVE

MOV COUNT R0

read_loop:
    PICK
    PUSH INV
    DEC R0
    CMP R0 0
    JNE read_loop

; Move to Outbox at (4,1)
TURN L
TURN L
MOVE
MOVE
MOVE
MOVE

MOV COUNT R0

pop_loop:
    POP R1
    MOV R1 INV
    DROP
    DEC R0
    CMP R0 0
    JNE pop_loop

HLT
