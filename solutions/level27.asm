; Level 27: Virtual Memory Paging & TLB Solution
; Page Table: Page 0 -> 10, Page 1 -> 20, Page 2 -> 30, Page 3 -> 40

DB 10 20 30 40

MOVE
MOVE ; At Inbox (0,1)

page_loop:
    PICK
    MOV INV R0 ; Virtual Page

    LOAD R0 INV ; Physical Frame = RAM[Virtual Page]

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

    JMP page_loop
