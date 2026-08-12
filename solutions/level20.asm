; Level 20: The Grand Teleportation Citadel Solution
; 1. Pick key at (0,0), move to Button (3,0), drop key to hold Door (3,2) open.
; 2. Move to Portal (4,0) to teleport to (2,2).
; 3. Move to Inbox (0,2), filter even numbers onto Stack, pop in reverse to Outbox (4,2).

PICK ; Pick key item at (0,0)
MOVE
MOVE
MOVE ; At Button (3,0)
DROP ; Drop key on Button -> Door (3,2) open permanently!
MOVE ; Step on Portal (4,0) -> Teleported to (2,2) facing E

TURN L
TURN L
MOVE
MOVE ; At Inbox (0,2) facing W

MOV 4 R2 ; 4 items

process_loop:
    PICK
    MOV INV R0
    MOV R0 R1
    AND 1 R1 ; check if odd
    CMP R1 0
    JNE skip_odd
    PUSH R0

skip_odd:
    DEC R2
    CMP R2 0
    JNE process_loop

; Move through open Door (3,2) to Outbox (4,2)
TURN L
TURN L
MOVE
MOVE
MOVE
MOVE ; At Outbox (4,2) facing E

MOV 2 R3 ; 2 even items in stack

pop_loop:
    POP INV
    DROP
    DEC R3
    CMP R3 0
    JNE pop_loop

HLT
