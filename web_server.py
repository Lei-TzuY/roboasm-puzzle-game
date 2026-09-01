import glob
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from assembler import Assembler, AssemblerError
from disassembler import Disassembler
from lexer import Lexer, LexerError
from runtime_api import execute_level_code

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_ASSET_NAMES = {
    'web_optimizer.js',
    'web_preprocessor.js',
    'web_runtime_compat.js',
    'web_authority.js',
}


def resolve_level_path(level_file):
    """Resolve a client-supplied level filename without allowing path traversal."""
    if not isinstance(level_file, str) or not level_file.strip():
        raise ValueError("Missing 'level' field")

    safe_name = os.path.basename(level_file.strip())
    if not safe_name.endswith('.json'):
        raise ValueError("level must name a .json file")

    level_path = os.path.join(ROOT_DIR, 'levels', safe_name)
    if not os.path.isfile(level_path):
        raise FileNotFoundError(f"Level '{safe_name}' not found")
    return level_path


def collect_web_include_sources():
    """Return UTF-8 project-local assembly sources available to Web #include."""
    sources = {}
    skipped_dirs = {'.git', '__pycache__', '.pytest_cache'}

    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        dirnames[:] = [
            name for name in dirnames
            if name not in skipped_dirs and not name.startswith('.')
        ]
        for filename in filenames:
            if not filename.lower().endswith('.asm'):
                continue
            absolute = os.path.join(dirpath, filename)
            relative = os.path.relpath(absolute, ROOT_DIR).replace(os.sep, '/')
            try:
                with open(absolute, 'r', encoding='utf-8') as handle:
                    sources[relative] = handle.read()
            except (OSError, UnicodeError):
                continue
    return sources


def build_web_runtime_bootstrap(html):
    """Install compiler/runtime layers before the server-served IDE initializes."""
    init_marker = '\ninitUI();\n</script>'
    init_deferred = init_marker in html
    if init_deferred:
        html = html.replace(
            init_marker,
            '\nglobalThis.__ROBOASM_INIT_DEFERRED__ = true;\n</script>',
            1,
        )

    include_json = json.dumps(
        collect_web_include_sources(),
        ensure_ascii=True,
        separators=(',', ':'),
    ).replace('</', '<\\/')
    runtime_tags = [
        f'<script>globalThis.ROBOASM_WEB_INCLUDE_SOURCES={include_json};</script>',
        '<script src="/web_optimizer.js"></script>',
        '<script src="/web_preprocessor.js"></script>',
        '<script src="/web_runtime_compat.js"></script>',
        '<script src="/web_authority.js"></script>',
    ]
    if init_deferred:
        runtime_tags.append('<script>initUI();</script>')

    injected = '\n'.join(runtime_tags)
    if '</body>' in html:
        return html.replace('</body>', f'{injected}\n</body>', 1)
    return f'{html}\n{injected}\n'


class RoboASMRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self._send_bytes(status, body, 'application/json; charset=utf-8')

    def _read_json(self):
        content_length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query = urllib.parse.parse_qs(parsed_path.query)

        if path in ('/', '/index.html', '/web_ui.html'):
            ui_path = os.path.join(ROOT_DIR, 'web_ui.html')
            with open(ui_path, 'r', encoding='utf-8') as f:
                html = build_web_runtime_bootstrap(f.read())
            self._send_bytes(200, html.encode('utf-8'), 'text/html; charset=utf-8')

        elif path.startswith('/') and os.path.basename(path) in WEB_ASSET_NAMES:
            asset_name = os.path.basename(path)
            asset_path = os.path.join(ROOT_DIR, asset_name)
            with open(asset_path, 'rb') as f:
                body = f.read()
            self._send_bytes(200, body, 'application/javascript; charset=utf-8')

        elif path == '/api/levels':
            levels_dir = os.path.join(ROOT_DIR, 'levels')
            level_files = glob.glob(os.path.join(levels_dir, "*.json"))

            def get_lvl_num(filename):
                match = re.search(r'\d+', os.path.basename(filename))
                return int(match.group()) if match else 0

            level_files.sort(key=get_lvl_num)
            levels = []
            for level_file in level_files:
                try:
                    with open(level_file, 'r', encoding='utf-8') as f:
                        level_data = json.load(f)
                        level_data['filename'] = os.path.basename(level_file)
                        levels.append(level_data)
                except Exception as exc:
                    print(f"Error loading level {level_file}: {exc}")
            self._send_json(200, levels)

        elif path == '/api/solutions':
            level_file = query.get('level', [''])[0]
            if not level_file:
                self._send_json(400, {'status': 'error', 'error': "Missing 'level' query parameter"})
                return
            level_file = os.path.basename(level_file)
            sol_filename = level_file.replace('.json', '.asm')
            sol_path = os.path.join(ROOT_DIR, 'solutions', sol_filename)
            code = ""
            if os.path.exists(sol_path):
                try:
                    with open(sol_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                except Exception as exc:
                    print(f"Error reading solution {sol_path}: {exc}")
            self._send_json(200, {"code": code})

        elif path == '/api/profile':
            profile_path = os.path.join(ROOT_DIR, 'profile.json')
            profile = {}
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile = json.load(f)
                except Exception as exc:
                    print(f"Error reading profile: {exc}")
            self._send_json(200, profile)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == '/api/assemble':
            try:
                data = self._read_json()
                code = data.get('code', '')
                optimize = data.get('optimize', False)
                if not isinstance(code, str):
                    raise ValueError("code must be a string")
                if not isinstance(optimize, bool):
                    raise ValueError("optimize must be a boolean")
                lexer = Lexer(code)
                tokens = lexer.tokenize()
                assembler = Assembler(tokens, base_dir=ROOT_DIR)
                instructions = assembler.assemble(optimize=optimize)
                self._send_json(200, {
                    "status": "success",
                    "optimized": optimize,
                    "instructions": instructions,
                    "symbol_table": assembler.symbol_table,
                    "data_memory": assembler.data_memory,
                })
            except (LexerError, AssemblerError) as exc:
                self._send_json(400, {"status": "error", "error": str(exc), "line_num": getattr(exc, 'line_num', None)})
            except ValueError as exc:
                self._send_json(400, {"status": "error", "error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"status": "error", "error": f"Internal assembly error: {exc}"})

        elif path == '/api/run':
            try:
                data = self._read_json()
                level_path = resolve_level_path(data.get('level'))
                result = execute_level_code(
                    data.get('code', ''), level_path,
                    max_cycles=data.get('max_cycles', 1000),
                    capture_trace=data.get('capture_trace', False),
                    optimize=data.get('optimize', False),
                    source_base_dir=ROOT_DIR,
                )
                self._send_json(200, result)
            except FileNotFoundError as exc:
                self._send_json(404, {"status": "error", "error": str(exc)})
            except (LexerError, AssemblerError) as exc:
                self._send_json(400, {"status": "error", "error": str(exc), "line_num": getattr(exc, 'line_num', None)})
            except ValueError as exc:
                self._send_json(400, {"status": "error", "error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"status": "error", "error": f"Internal execution error: {exc}"})

        elif path == '/api/disassemble':
            try:
                data = self._read_json()
                instructions = data.get('instructions', [])
                symbol_table = data.get('symbol_table', {})
                disasm = Disassembler(instructions, symbol_table)
                code = disasm.disassemble()
                self._send_json(200, {"status": "success", "code": code})
            except ValueError as exc:
                self._send_json(400, {"status": "error", "error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"status": "error", "error": str(exc)})

        elif path == '/api/solutions':
            try:
                data = self._read_json()
                level_file = data.get('level')
                code = data.get('code', '')
                if not isinstance(level_file, str) or not level_file:
                    raise ValueError("Missing 'level' in request body")
                if not isinstance(code, str):
                    raise ValueError("code must be a string")
                level_file = os.path.basename(level_file)
                sol_filename = level_file.replace('.json', '.asm')
                solutions_dir = os.path.join(ROOT_DIR, 'solutions')
                os.makedirs(solutions_dir, exist_ok=True)
                sol_path = os.path.join(solutions_dir, sol_filename)
                with open(sol_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                self._send_json(200, {"status": "success"})
            except ValueError as exc:
                self._send_json(400, {"status": "error", "error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"status": "error", "error": f"Error saving solution: {exc}"})

        elif path == '/api/profile':
            try:
                import time
                data = self._read_json()
                level_file = data.get('level')
                cycles = data.get('cycles')
                size = data.get('size')
                if not level_file or cycles is None or size is None:
                    raise ValueError("Missing required fields in request body")
                level_file = os.path.basename(level_file)
                profile_path = os.path.join(ROOT_DIR, 'profile.json')
                profile = {}
                if os.path.exists(profile_path):
                    try:
                        with open(profile_path, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                    except Exception:
                        pass
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
                profile[level_file]['history'].append({'timestamp': int(time.time()), 'cycles': cycles, 'size': size})
                if len(profile[level_file]['history']) > 30:
                    profile[level_file]['history'].pop(0)
                with open(profile_path, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2)
                self._send_json(200, {"status": "success", "new_record": new_record, "profile": profile})
            except ValueError as exc:
                self._send_json(400, {"status": "error", "error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"status": "error", "error": f"Error saving profile: {exc}"})
        else:
            self.send_error(404, "Not found")


def start_web_server(port=8000):
    server = HTTPServer(('127.0.0.1', port), RoboASMRequestHandler)
    print(f"RoboASM Web IDE Server running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb Server stopped.")
