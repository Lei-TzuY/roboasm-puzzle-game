; Level 26: Shortest Path Routing Solution
; RAM 0..3: 0 5 2 10

DB 0 5 2 10

MOVE
MOVE ; At Inbox (0,1)

route_loop:
    PICK
    MOV INV R0 ; Dest node index

    LOAD R0 INV ; Look up distance RAM[R0]

    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE ; At Outbox (4,1)
    DROP
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    MOVE ; Return to Inbox (0,1)

    JMP route_loop
