// Level 6 Solution: The Vault
    MOV Y, R0
    CMP R0, 2
    JEQ ROBOT_ONE

ROBOT_ZERO:
    // Start at (1,0) facing E. Button is at (3,0).
    MOVE
    MOVE
LOOP_ZERO:
    // We are on the button (3,0).
    // The door at (3,2) is open!
    // We just stay here forever.
    JMP LOOP_ZERO

ROBOT_ONE:
    // Start at (1,2) facing E. Inbox is at (0,2).
    TURN L
    TURN L
    MOVE
    
LOOP_ONE:
    // We are at (0,2) facing W.
    PICK
    
    // Call the subroutine to square the number
    CALL SQUARE_IT
    
    // Turn back facing East
    TURN L
    TURN L
    
    // Move to outbox at (5,2)
    MOVE
    MOVE
    MOVE
    MOVE
    MOVE
    DROP
    
    // Move back to (0,2)
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    MOVE
    
    JMP LOOP_ONE

SQUARE_IT:
    // Multiply INV by itself
    MUL INV, INV
    RET
