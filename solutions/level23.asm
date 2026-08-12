; Level 23: RPN Stack Calculator Solution
; Token queue: 5 3 -1 4 -3 -99
; -1 = ADD, -2 = SUB, -3 = MUL, -99 = END

MOVE
MOVE ; At Inbox (0,1)

rpn_loop:
    PICK
    MOV INV R0

    CMP R0 -99
    JEQ output_result

    CMP R0 -1
    JEQ do_add

    CMP R0 -2
    JEQ do_sub

    CMP R0 -3
    JEQ do_mul

    ; Positive number operand -> PUSH R0
    PUSH R0
    JMP rpn_loop

do_add:
    POP R2 ; v2
    POP R1 ; v1
    ADD R2 R1 ; R1 = v1 + v2
    PUSH R1
    JMP rpn_loop

do_sub:
    POP R2 ; v2
    POP R1 ; v1
    SUB R2 R1 ; R1 = v1 - v2
    PUSH R1
    JMP rpn_loop

do_mul:
    POP R2 ; v2
    POP R1 ; v1
    MUL R2 R1 ; R1 = v1 * v2
    PUSH R1
    JMP rpn_loop

output_result:
    POP INV
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE ; At Outbox (4,1)
    DROP
    HLT
