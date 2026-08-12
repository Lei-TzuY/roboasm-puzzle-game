; Level 14: Bitwise Masker Solution
; Move to Inbox at (0,1), pick item, mask lower 4 bits & right-shift by 1, move to Outbox at (4,1) and drop

; Move to Inbox at (0,1)
MOVE
MOVE

start:
    PICK
    MOV INV R0
    AND 15 R0
    SHR R0 1
    MOV R0 INV
    
    ; Move to Outbox (4,1)
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    
    DROP
    
    ; Return to Inbox (0,1)
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    
    JMP start
