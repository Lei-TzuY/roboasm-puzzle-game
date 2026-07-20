// Level 3 Solution: Zero Eliminator
// Start at (2,1) facing W.
    MOVE
    MOVE
LOOP:
    // At (0,1) facing W
    PICK
    
    // Compare INV with 0
    CMP INV, 0
    
    // If <= 0, discard it
    JEQ DISCARD
    JLT DISCARD
    
    // It's positive! Send to outbox.
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    DROP
    
    // Return to inbox
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    JMP LOOP
    
DISCARD:
    // Turn South, move to (0,2), drop item to overwrite the floor junk
    TURN L
    MOVE
    DROP
    
    // Return to Inbox (0,1) facing W
    TURN L
    TURN L
    MOVE
    TURN L
    JMP LOOP
