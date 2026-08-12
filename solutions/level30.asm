; Level 30: Self-Hosting Compiler Bootstrapper Solution
; Tokens: 101 -> 1, 102 -> 2, 103 -> 9, 999 -> END

MOVE
MOVE ; At Inbox (0,1)

compile_loop:
    PICK
    MOV INV R0

    CMP R0 999
    JEQ compile_done

    CMP R0 101
    JEQ emit_mov

    CMP R0 102
    JEQ emit_add

    CMP R0 103
    JEQ emit_hlt

    ; Literal operand -> pass through
    MOV R0 INV
    JMP emit_bytecode

emit_mov:
    MOV 1 INV
    JMP emit_bytecode

emit_add:
    MOV 2 INV
    JMP emit_bytecode

emit_hlt:
    MOV 9 INV

emit_bytecode:
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE ; At Outbox (4,1)
    DROP
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE ; Return to Inbox (0,1)

    JMP compile_loop

compile_done:
    HLT
