import re

class Lexer:
    def __init__(self, code):
        self.code = code
        self.tokens = []

    def tokenize(self):
        lines = self.code.split('\n')
        for line_num, line in enumerate(lines, 1):
            line = re.split(r'//|;|#', line)[0].strip()
            if not line:
                continue
            
            # Simple tokenization: split by spaces and commas
            parts = [p.strip() for p in re.split(r'[ \t,]+', line) if p.strip()]
            
            if parts:
                self.tokens.append({'line_num': line_num, 'parts': parts})
        return self.tokens
