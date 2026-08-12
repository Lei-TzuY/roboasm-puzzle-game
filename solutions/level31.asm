; Level 31: Dynamic Memory Allocator (malloc) Solution
; RAM 0 = free_ptr (10)

DB 10

MOVE
MOVE ; At Inbox (0,1)

PICK
MOV INV R0 ; size = 2

LOAD 0 R1  ; R1 = allocated ptr (10)

; Store 100 at RAM[10], 200 at RAM[11]
MOV 100 INV
STORE INV R1

MOV R1 R2
INC R2     ; R2 = 11
MOV 200 INV
STORE INV R2

; Advance free_ptr: RAM[0] = 10 + 2 = 12
MOV R1 R3
ADD R0 R3
STORE R3 0

; Output allocated ptr (10) and sum (300)
MOV R1 INV
TURN L
TURN L
MOVE
MOVE
MOVE
MOVE ; At Outbox (4,1)
DROP

MOV 300 INV
DROP
HLT
