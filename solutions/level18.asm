; Level 18: 2D Matrix Map Solution
; Compute 2D Index: Y * 3 + X and LOAD from RAM data

DB 10 20 30 40 50 60 70 80 90

MOVE
MOVE ; Move to Inbox (0,1)

PICK
MOV INV R0 ; X
PICK
MOV INV R1 ; Y

MUL 3 R1   ; Y * 3
ADD R0 R1  ; Y * 3 + X

LOAD R1 INV

TURN L
TURN L
MOVE
MOVE
MOVE
MOVE
DROP
HLT
