; Level 25: Microkernel Context Switcher Solution
; RAM 0..3: PCB 1 (11, 22, 33, 44)
; RAM 4..7: PCB 2 (55, 66, 77, 88)

DB 11 22 33 44 55 66 77 88

MOVE
MOVE ; At Inbox (0,1)

kernel_loop:
    PICK
    MOV INV R0 ; PID (1 or 2)

    CMP R0 1
    JEQ switch_p1

switch_p2:
    MOV 4 R0 ; Base address = 4
    JMP execute_context_switch

switch_p1:
    MOV 0 R0 ; Base address = 0

execute_context_switch:
    ; Restore Context into R0..R3
    MOV R0 R1
    INC R1
    MOV R0 R2
    ADD 2 R2
    MOV R0 R3
    ADD 3 R3

    LOAD R0 R0 ; R0 = RAM[base]
    LOAD R1 R1 ; R1 = RAM[base+1]
    LOAD R2 R2 ; R2 = RAM[base+2]
    LOAD R3 R3 ; R3 = RAM[base+3]

    ; Increment context state
    INC R0
    INC R1
    INC R2
    INC R3

    ; Compute total sum into INV
    MOV R0 INV
    ADD R1 INV
    ADD R2 INV
    ADD R3 INV

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

    JMP kernel_loop
