import os
import json
import re
import glob
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

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
                        # Add filename property so frontend knows which file this corresponds to
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
            
        # API: Save new custom level
        elif path == '/api/levels':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                filename = data.get('filename')
                if not filename:
                    self.send_error(400, "Missing 'filename' in request body")
                    return
                
                filename = os.path.basename(filename)
                if not filename.endswith('.json'):
                    filename += '.json'
                
                levels_dir = os.path.join(os.path.dirname(__file__), 'levels')
                os.makedirs(levels_dir, exist_ok=True)
                lvl_path = os.path.join(levels_dir, filename)
                
                level_def = data.get('level_def')
                if not level_def:
                    self.send_error(400, "Missing 'level_def' in request body")
                    return
                
                with open(lvl_path, 'w', encoding='utf-8') as f:
                    json.dump(level_def, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "filename": filename}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Error saving level: {e}")
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        # API: Save solution for a level
        if path == '/api/solutions':
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
                
                # Append to history list
                profile[level_file]['history'].append({
                    'timestamp': int(time.time()),
                    'cycles': cycles,
                    'size': size
                })
                if len(profile[level_file]['history']) > 30:
                    profile[level_file]['history'].pop(0)
                
                # Always save profile.json since history updates
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
