; Level 33: Self-Modifying Code Simulation Solution
; RAM 0 = 50, RAM 1 = 20

DB 50 20

MOVE
MOVE ; At Inbox (0,1)

PICK
STORE INV 2 ; Store patch opcode 1 into RAM[2]

LOAD 0 R0 ; R0 = 50
LOAD 1 R1 ; R1 = 20
LOAD 2 R2 ; R2 = patched opcode (1)

CMP R2 1
JEQ do_patched_add

do_patched_sub:
    SUB R1 R0
    JMP emit_result

do_patched_add:
    ADD R1 R0

emit_result:
    MOV R0 INV
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE ; At Outbox (4,1)
    DROP
    HLT
