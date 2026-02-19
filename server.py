import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
PROJECTS_ROOT = os.getenv("GIT_PROJECT_ROOT", "/git-repos")

# ignore permissions
subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', '*'])
subprocess.run(['git', 'config', '--system', '--add', 'safe.directory', '*'])

backend = subprocess.check_output(['git', '--exec-path']).decode().strip()
backend_path = os.path.join(backend, 'git-http-backend')

class GitRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.endswith("/"):
            self.list_repos()
        else:
            self.handle_git()

    def list_repos(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        repos = [d for d in os.listdir(PROJECTS_ROOT) if os.path.isdir(os.path.join(PROJECTS_ROOT, d))]
        
        html = f"<html><body><h1>Available Repositories</h1><ul>"
        for r in repos:
            html += f"<li><a href='/{r}/info/refs?service=git-upload-pack'>{r}</a></li>"
        html += "</ul><p>Clone via: <code>git clone http://localhost:8080/YOUR_REPO_NAME</code></p></body></html>"
        
        self.wfile.write(html.encode())

    def do_POST(self):
        self.handle_git()

    def handle_git(self):
        env = {
            'REQUEST_METHOD': self.command,
            'GIT_PROJECT_ROOT': PROJECTS_ROOT,
            'GIT_HTTP_EXPORT_ALL': '1',
            'PATH_INFO': self.path.split('?')[0],
            'QUERY_STRING': self.path.split('?')[1] if '?' in self.path else '',
            'REMOTE_ADDR': self.client_address[0],
        }

        for key, value in self.headers.items():
            env_key = f"HTTP_{key.upper().replace('-', '_')}"
            env[env_key] = value
        
        if 'Content-Type' in self.headers:
            env['CONTENT_TYPE'] = self.headers['Content-Type']
        if 'Content-Length' in self.headers:
            env['CONTENT_LENGTH'] = self.headers['Content-Length']

        content_length = int(self.headers.get('Content-Length', 0))
        input_data = self.rfile.read(content_length) if content_length > 0 else None

        proc = subprocess.Popen(
            [backend_path],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout_data, stderr_data = proc.communicate(input=input_data)

        delimiter = b'\r\n\r\n' if b'\r\n\r\n' in stdout_data else b'\n\n'
        parts = stdout_data.split(delimiter, 1)
        
        header_part = parts[0]
        body = parts[1] if len(parts) > 1 else b''

        status_code = 200
        response_headers = []
        for line in header_part.splitlines():
            if b':' in line:
                k, v = line.split(b':', 1)
                k_str, v_str = k.decode().strip(), v.decode().strip()
                if k_str.lower() == 'status':
                    status_code = int(v_str.split(' ')[0])
                else:
                    response_headers.append((k_str, v_str))

        self.send_response(status_code)
        for k, v in response_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

        if stderr_data:
            print(f"Backend Error: {stderr_data.decode('utf-8', errors='replace')}", file=sys.stderr)

print(f"")
print(f"--- Filesystem git HTTP bridge ---")
print(f"Backend: {backend_path}")
print(f"Serving from: {PROJECTS_ROOT}")
print(f"URL: http://localhost:{PORT}/<your-repo-name>")
print(f"----------------------------------")
print(f"")

HTTPServer(('0.0.0.0', PORT), GitRequestHandler).serve_forever()
