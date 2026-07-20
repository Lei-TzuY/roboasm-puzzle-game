// Level 11 Solution: Pattern Matcher
@define TARGET 99

    // Initialize index counter R0 to 0
    MOV 0 R0

LOOP:
    // Move to Inbox at (0,1)
    MOVE
    MOVE
    PICK
    
    // Compare INV with TARGET (99)
    CMP INV TARGET
    JEQ FOUND
    
    // Increment index counter R0
    ADD 1 R0
    
    // Move E and drop non-matching item at (1,1)
    TURN R
    TURN R
    MOVE
    DROP
    MOVE
    
    // Turn back W and repeat
    TURN R
    TURN R
    JMP LOOP

FOUND:
    // Move E and drop the target item at (1,1)
    TURN R
    TURN R
    MOVE
    DROP
    
    // Move E to Outbox at (4,1)
    MOVE
    MOVE
    MOVE
    
    // Output the index counter R0
    MOV R0 INV
    DROP
    HLT
