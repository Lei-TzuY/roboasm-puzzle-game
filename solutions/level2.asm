// Level 2 Solution: Doubler
// Start at (2,1) facing W. Inbox is at (0,1)
    MOVE
    MOVE
LOOP:
    // At (0,1) facing W
    PICK
    
    // Double the value in our hands
    ADD INV, INV
    
    // Move to outbox at (4,1)
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    
    // Drop value
    DROP
    
    // Return to Inbox
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    
    JMP LOOP
