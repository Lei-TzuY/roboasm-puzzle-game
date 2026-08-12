import os
import json
import re
import glob
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

from lexer import Lexer, LexerError
from assembler import Assembler, AssemblerError
from disassembler import Disassembler

class RoboASMRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress request logging to keep the console clean
        pass

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query = urllib.parse.parse_qs(parsed_path.query)

        # Serve index/web UI
        if path in ('/', '/index.html', '/web_ui.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            ui_path = os.path.join(os.path.dirname(__file__), 'web_ui.html')
            with open(ui_path, 'rb') as f:
                self.wfile.write(f.read())
                
        # API: Get all levels dynamically
        elif path == '/api/levels':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            levels_dir = os.path.join(os.path.dirname(__file__), 'levels')
            level_files = glob.glob(os.path.join(levels_dir, "*.json"))
            
            def get_lvl_num(f):
                m = re.search(r'\d+', os.path.basename(f))
                return int(m.group()) if m else 0
            
            level_files.sort(key=get_lvl_num)
            
            levels = []
            for lf in level_files:
                try:
                    with open(lf, 'r', encoding='utf-8') as f:
                        level_data = json.load(f)
                        level_data['filename'] = os.path.basename(lf)
                        levels.append(level_data)
                except Exception as e:
                    print(f"Error loading level {lf}: {e}")
            
            self.wfile.write(json.dumps(levels).encode('utf-8'))
            
        # API: Load solution for a level
        elif path == '/api/solutions':
            level_file = query.get('level', [''])[0]
            if not level_file:
                self.send_error(400, "Missing 'level' query parameter")
                return
            
            level_file = os.path.basename(level_file)
            sol_filename = level_file.replace('.json', '.asm')
            sol_path = os.path.join(os.path.dirname(__file__), 'solutions', sol_filename)
            
            code = ""
            if os.path.exists(sol_path):
                try:
                    with open(sol_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                except Exception as e:
                    print(f"Error reading solution {sol_path}: {e}")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"code": code}).encode('utf-8'))
            
        # API: Load scoreboard profile
        elif path == '/api/profile':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            profile_path = os.path.join(os.path.dirname(__file__), 'profile.json')
            profile = {}
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile = json.load(f)
                except Exception as e:
                    print(f"Error reading profile: {e}")
            self.wfile.write(json.dumps(profile).encode('utf-8'))
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # API: Assemble code via Python Assembler
        if path == '/api/assemble':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                code = data.get('code', '')

                lexer = Lexer(code)
                tokens = lexer.tokenize()
                assembler = Assembler(tokens)
                instructions = assembler.assemble()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "instructions": instructions,
                    "symbol_table": assembler.symbol_table,
                    "data_memory": assembler.data_memory
                }).encode('utf-8'))
            except (LexerError, AssemblerError) as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": str(e),
                    "line_num": getattr(e, 'line_num', None)
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "error": f"Internal assembly error: {e}"
                }).encode('utf-8'))

        # API: Disassemble instructions to code
        elif path == '/api/disassemble':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                instructions = data.get('instructions', [])
                symbol_table = data.get('symbol_table', {})

                disasm = Disassembler(instructions, symbol_table)
                code = disasm.disassemble()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "code": code
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "error": str(e)}).encode('utf-8'))
        
        # API: Save solution for a level
        elif path == '/api/solutions':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                level_file = data.get('level')
                code = data.get('code', '')
                if not level_file:
                    self.send_error(400, "Missing 'level' in request body")
                    return
                
                level_file = os.path.basename(level_file)
                sol_filename = level_file.replace('.json', '.asm')
                solutions_dir = os.path.join(os.path.dirname(__file__), 'solutions')
                os.makedirs(solutions_dir, exist_ok=True)
                
                sol_path = os.path.join(solutions_dir, sol_filename)
                with open(sol_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Error saving solution: {e}")
                
        # API: Save/Update personal best profile records
        elif path == '/api/profile':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                import time
                data = json.loads(post_data.decode('utf-8'))
                level_file = data.get('level')
                cycles = data.get('cycles')
                size = data.get('size')
                if not level_file or cycles is None or size is None:
                    self.send_error(400, "Missing required fields in request body")
                    return
                
                level_file = os.path.basename(level_file)
                profile_path = os.path.join(os.path.dirname(__file__), 'profile.json')
                profile = {}
                if os.path.exists(profile_path):
                    try:
                        with open(profile_path, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                    except: pass
                
                new_record = False
                if level_file not in profile:
                    profile[level_file] = {'best_cycles': cycles, 'best_size': size, 'history': []}
                    new_record = True
                else:
                    if 'history' not in profile[level_file]:
                        profile[level_file]['history'] = []
                    if cycles < profile[level_file]['best_cycles']:
                        profile[level_file]['best_cycles'] = cycles
                        new_record = True
                    if size < profile[level_file]['best_size']:
                        profile[level_file]['best_size'] = size
                        new_record = True
                
                profile[level_file]['history'].append({
                    'timestamp': int(time.time()),
                    'cycles': cycles,
                    'size': size
                })
                if len(profile[level_file]['history']) > 30:
                    profile[level_file]['history'].pop(0)
                
                with open(profile_path, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "new_record": new_record, "profile": profile}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Error saving profile: {e}")
        else:
            self.send_error(404, "Not found")

def start_web_server(port=8000):
    server = HTTPServer(('127.0.0.1', port), RoboASMRequestHandler)
    print(f"RoboASM Web IDE Server running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb Server stopped.")
