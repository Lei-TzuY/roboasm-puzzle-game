; Level 22: Binary Search Solution
; Sorted array in RAM 0..7: 3 8 15 24 35 48 63 80
; Search targets from Inbox: 15 -> 2, 48 -> 5, 99 -> -1

DB 3 8 15 24 35 48 63 80

MOVE
MOVE ; At Inbox (0,1)

search_task_loop:
    PICK
    MOV INV R0 ; target X in R0

    MOV 0 R1 ; L = 0
    MOV 7 R2 ; R = 7

bsearch_loop:
    CMP R1 R2
    JGT not_found ; L > R

    MOV R1 R3
    ADD R2 R3
    DIV 2 R3   ; R3 = Mid = (L + R) // 2

    LOAD R3 INV ; INV = RAM[Mid]
    CMP INV R0  ; Compare RAM[Mid] vs Target X
    JEQ found

    CMP R0 INV
    JLT search_left

search_right:
    ; Target > RAM[Mid] -> L = Mid + 1
    MOV R3 R1
    INC R1
    JMP bsearch_loop

search_left:
    ; Target < RAM[Mid] -> R = Mid - 1
    MOV R3 R2
    DEC R2
    JMP bsearch_loop

found:
    MOV R3 INV
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
    JMP search_task_loop

not_found:
    MOV -1 INV
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
    JMP search_task_loop
