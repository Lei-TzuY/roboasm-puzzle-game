; Level 34: FFT Butterfly Unit Solution
; A = 12, B = 5 -> X = A + B = 17, Y = A - B = 7

MOVE
MOVE ; At Inbox (0,1)

PICK
MOV INV R0 ; A = 12

PICK
MOV INV R1 ; B = 5

; Compute X = A + B
MOV R0 R2
ADD R1 R2  ; R2 = 17

; Compute Y = A - B
MOV R0 R3
SUB R1 R3  ; R3 = 7

MOV R2 INV
TURN L
TURN L
MOVE
MOVE
MOVE
MOVE ; At Outbox (4,1)
DROP

MOV R3 INV
DROP
HLT
