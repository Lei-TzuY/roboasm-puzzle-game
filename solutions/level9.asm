// Level 9 Solution: Prime Tester
START:
    // Move to Inbox at (0,1)
    MOVE
    MOVE
    PICK
    MOV INV R0 // R0 is X
    
    // If X <= 1, not prime
    CMP R0 1
    JLT NOT_PRIME
    JEQ NOT_PRIME
    
    // If X == 2, is prime
    CMP R0 2
    JEQ IS_PRIME
    
    // If X == 3, is prime
    CMP R0 3
    JEQ IS_PRIME
    
    // If X % 2 == 0, not prime
    MOV 2 R1
    MOV R0 R2
    MOD R1 R2 // R2 = X % 2
    CMP R2 0
    JEQ NOT_PRIME
    
    // Loop test odd numbers starting from 3
    MOV 3 R1 // R1 is divisor i
LOOP_TEST:
    // If i * i > X, then it is prime
    MOV R1 R2
    MUL R1 R2 // R2 = i * i
    CMP R2 R0 // compare i*i with X
    JGT IS_PRIME
    
    // Check if X % i == 0
    MOV R0 R2
    MOD R1 R2 // R2 = X % i
    CMP R2 0
    JEQ NOT_PRIME
    
    // i = i + 2
    ADD 2 R1
    JMP LOOP_TEST
    
IS_PRIME:
    MOV 1 R3
    JMP OUTPUT
    
NOT_PRIME:
    MOV 0 R3
    JMP OUTPUT
    
OUTPUT:
    // Move to Outbox at (4,1)
    TURN R
    TURN R
    MOVE
    MOVE
    MOVE
    MOVE
    MOV R3 INV
    DROP
    
    // Return to Inbox at (0,1)
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE
    JMP START
