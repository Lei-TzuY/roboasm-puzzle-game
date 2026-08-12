; Level 28: Stream Cipher Cryptography Solution
; Key = 15. Ciphertext = Plaintext ^ 15

#define KEY 15

MOVE
MOVE ; At Inbox (0,1)

cipher_loop:
    PICK
    MOV INV R0
    XOR KEY R0

    MOV R0 INV
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

    JMP cipher_loop
