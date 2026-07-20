// Level 5 Solution: The Relay
    MOV X, R0
    CMP R0, 3
    JLT ROBOT_ZERO

ROBOT_ONE:
    // Robot 1: Starts at (5,1) facing W.
LOOP_ONE:
    // Pick from end of conveyor (5,1)
    PICK
    
    // Go to outbox (6,1)
    TURN L
    TURN L
    MOVE
    DROP
    
    // Return to (5,1)
    TURN L
    TURN L
    MOVE
    JMP LOOP_ONE

ROBOT_ZERO:
    // Robot 0: Starts at (1,1) facing W.
    // Move to Inbox (0,1)
    MOVE
LOOP_ZERO:
    // Pick from Inbox
    PICK
    
    // Move to start of Conveyor (2,1)
    TURN L
    TURN L
    MOVE
    MOVE
    DROP
    
    // Return to Inbox
    TURN L
    TURN L
    MOVE
    MOVE
    JMP LOOP_ZERO
