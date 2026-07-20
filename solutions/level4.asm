// Level 4 Solution: The Factory Line
// Start at (2,1) facing W.
    MOVE
    MOVE
LOOP:
    // At (0,1) facing W
    PICK
    
    // Move to Conveyor at (4,1)
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    
    // Drop item on the conveyor
    DROP
    
    // Return to Inbox
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    
    JMP LOOP
