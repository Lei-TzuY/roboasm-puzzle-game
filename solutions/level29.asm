; Level 29: Fixed-Point Math Engine (Q8.8) Solution
; A = 512, B = 1024 -> Result = (512 * 1024) >> 8 = 524288 >> 8 = 2048

MOVE
MOVE ; At Inbox (0,1)

PICK
MOV INV R0 ; A

PICK
MOV INV R1 ; B

MUL R1 R0  ; R0 = A * B
SHR R0 8   ; R0 = R0 >> 8

MOV R0 INV
TURN L
TURN L
MOVE
MOVE
MOVE
MOVE ; At Outbox (4,1)
DROP
HLT
