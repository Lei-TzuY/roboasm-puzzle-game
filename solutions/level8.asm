// Level 8 Solution: Fibonaccier
    // Start at (2,1) facing W.
    MOVE
    MOVE
    PICK
    MOV INV R0
    
    // Initialize F(1) = 1, F(2) = 1
    MOV 1 R1
    MOV 1 R2

LOOP:
    CMP R0 0
    JEQ EXIT
    
    // Move to outbox at (4,1)
    TURN R
    TURN R
    MOVE
    MOVE
    MOVE
    MOVE
    
    // Output R1
    MOV R1 INV
    DROP
    
    // Decrement counter
    SUB 1 R0
    CMP R0 0
    JEQ EXIT
    
    // Calculate next Fibonacci term
    MOV R1 R3
    ADD R2 R3  // R3 = R1 + R2
    MOV R2 R1  // R1 = R2
    MOV R3 R2  // R2 = R3
    
    // Move back to (0,1)
    TURN R
    TURN R
    MOVE
    MOVE
    MOVE
    MOVE
    JMP LOOP

EXIT:
    HLT
