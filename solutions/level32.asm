; Level 32: Multi-Core Mutex Spinlock Solution
; Robot 0 (X=1), Robot 1 (X=5)

CMP X 5
JEQ r1_stage

r0_stage:
    MOVE ; Move to Inbox (0,1)
    PICK
    MOV INV R0 ; 10
    ADD 5 R0   ; 15

    ; Acquire Mutex Lock RAM[0]
acquire_lock_r0:
    LOAD 0 R1
    CMP R1 0
    JNE acquire_lock_r0

    STORE 1 0  ; Lock RAM[0] = 1
    STORE R0 1 ; RAM[1] = 15
    STORE 0 0  ; Unlock RAM[0] = 0

    SEND 1     ; Signal Robot 1
    HLT

r1_stage:
    RECV R0 ; Wait signal

acquire_lock_r1:
    LOAD 0 R1
    CMP R1 0
    JNE acquire_lock_r1

    STORE 1 0  ; Lock RAM[0] = 1
    LOAD 1 R2  ; R2 = RAM[1] (15)
    ADD 5 R2   ; 20
    STORE 0 0  ; Unlock RAM[0] = 0

    MOV R2 INV
    TURN L
    TURN L
    MOVE ; Move to Outbox (6,1)
    DROP
    HLT
