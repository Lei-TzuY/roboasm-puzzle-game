import re

class LexerError(Exception):
    def __init__(self, message, line_num=None, col_num=None):
        super().__init__(f"Lexer Error (Line {line_num or '?'}): {message}")
        self.line_num = line_num
        self.col_num = col_num

class Lexer:
    def __init__(self, code):
        self.code = code
        self.tokens = []

    def tokenize(self):
        self.tokens = []
        lines = self.code.split('\n')
        for line_num, raw_line in enumerate(lines, 1):
            # Split line by comment markers // or ;
            # If # is present, only treat as comment if it's not a directive (e.g. #define, #include, #ifdef, #ifndef, #else, #endif, #macro, #endmacro)
            line = raw_line
            # Remove // or ; comments
            line = re.split(r'//|;', line)[0]
            # Handle # comments vs #directives
            if '#' in line:
                # If # is at start or after whitespace followed by directive name, keep it. Otherwise treat # as comment.
                m = re.search(r'#(?:define|include|ifdef|ifndef|else|endif|macro|endmacro)\b', line, re.IGNORECASE)
                if not m:
                    line = line.split('#')[0]
            
            line = line.strip()
            if not line:
                continue
            
            # Tokenize: split by spaces and commas
            parts = [p.strip() for p in re.split(r'[ \t,]+', line) if p.strip()]
            
            if parts:
                self.tokens.append({
                    'line_num': line_num,
                    'raw_line': raw_line.strip(),
                    'parts': parts
                })
        return self.tokens
