; Level 21: Linked List Traversal Solution
; RAM 0 = head ptr (10). Node at ptr: val = RAM[ptr], next = RAM[ptr+1] (0 = end)

DB 10 0 0 0 0 0 0 0 0 0 42 20 0 0 0 0 0 0 0 0 99 30 0 0 0 0 0 0 0 0 7 0

MOVE
MOVE
MOVE
MOVE ; Move to Outbox (4,1)

LOAD 0 R0 ; R0 = head ptr (10)

traverse_loop:
    CMP R0 0
    JEQ done

    LOAD R0 INV ; INV = RAM[ptr] (node val)
    DROP        ; Drop node val into Outbox

    INC R0      ; R0 = ptr + 1
    LOAD R0 R0  ; R0 = RAM[ptr+1] (next ptr)
    JMP traverse_loop

done:
    HLT
