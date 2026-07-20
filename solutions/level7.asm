start:
    MOVE
    PICK
    TURN R
    TURN R
    MOVE
    CMP INV 0
    JLT negative

positive:
    TURN L
    MOVE
    MOVE
    MOVE
    DROP
    TURN R
    TURN R
    MOVE
    MOVE
    MOVE
    TURN R
    JMP start

negative:
    TURN R
    MOVE
    MOVE
    MOVE
    DROP
    TURN L
    TURN L
    MOVE
    MOVE
    MOVE
    TURN L
    JMP start
