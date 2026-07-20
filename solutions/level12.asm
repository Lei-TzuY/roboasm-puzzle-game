// Level 12 Solution: List Reverser
// Registers R0, R1, R2 store the list values.

    // 1. Move to Inbox at (0,1)
    MOVE
    MOVE
    PICK // Read N (3)
    
    // Turn N, move to (0,0) and drop N
    TURN R
    MOVE
    DROP
    
    // Move back to (0,1)
    TURN R
    TURN R
    MOVE
    
    // 2. Read first item
    PICK // Read 10
    MOV INV R0
    
    // Move to (0,2) and drop
    MOVE
    DROP
    
    // Move back to (0,1)
    TURN R
    TURN R
    MOVE
    
    // 3. Read second item
    PICK // Read 20
    MOV INV R1
    
    // Turn E, move to (1,1) and drop
    TURN R
    MOVE
    DROP
    
    // Move back to (0,1)
    TURN R
    TURN R
    MOVE
    
    // 4. Read third item
    PICK // Read 30
    MOV INV R2
    DROP // Drop right at (0,1) since we are done
    
    // 5. Move to Outbox at (4,1)
    TURN R
    TURN R
    MOVE
    MOVE
    MOVE
    MOVE
    
    // Write in reverse order
    MOV R2 INV
    DROP
    MOV R1 INV
    DROP
    MOV R0 INV
    DROP
    
    HLT
