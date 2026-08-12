; Level 17: Bubble Sort Solution
; Read 4 numbers into RAM 0..3, sort ascendingly, and output to Outbox

MOVE
MOVE ; Move to Inbox (0,1)

; Read 4 elements into RAM 0..3
PICK
STORE INV 0
PICK
STORE INV 1
PICK
STORE INV 2
PICK
STORE INV 3

pass_loop:
    MOV 0 R0 ; changed flag
    MOV 0 R1 ; ptr = 0

bubble_step:
    LOAD R1 R2      ; R2 = RAM[ptr]
    MOV R1 R3
    INC R3          ; R3 = ptr + 1
    LOAD R3 INV     ; INV = RAM[ptr+1]
    
    CMP INV R2      ; Compare RAM[ptr+1] vs RAM[ptr]
    JLT do_swap
    JMP next_step

do_swap:
    STORE INV R1
    STORE R2 R3
    MOV 1 R0

next_step:
    INC R1
    CMP R1 3
    JLT bubble_step

    CMP R0 0
    JNE pass_loop

; Move to Outbox (4,1)
TURN L
TURN L
MOVE
MOVE
MOVE
MOVE

; Output RAM 0..3
LOAD 0 INV
DROP
LOAD 1 INV
DROP
LOAD 2 INV
DROP
LOAD 3 INV
DROP
HLT
