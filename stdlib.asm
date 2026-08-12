; RoboASM Standard Macro Library (stdlib.asm)
; Common reusable assembly subroutines and macros

; Swap contents of two registers
%macro SWAP_REGS r1 r2
    SWAP r1 r2
%endmacro

; Compute absolute value of a register
%macro ABS_VAL reg
    ABS reg
%endmacro

; Store maximum of two registers into r2
%macro MAX_VAL r1 r2
    MAX r1 r2
%endmacro

; Store minimum of two registers into r2
%macro MIN_VAL r1 r2
    MIN r1 r2
%endmacro

; Increment register by 1
%macro INC_REG reg
    INC reg
%endmacro

; Decrement register by 1
%macro DEC_REG reg
    DEC reg
%endmacro
