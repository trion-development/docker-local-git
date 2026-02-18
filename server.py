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
            'CONTENT_TYPE': self.headers.get('Content-Type', ''),
            'REMOTE_ADDR': self.client_address[0],
        }

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

        if b'\r\n\r\n' in stdout_data:
            header_part, body = stdout_data.split(b'\r\n\r\n', 1)
        else:
            header_part, body = stdout_data.split(b'\n\n', 1)

        headers = []
        status_code = 200
        for line in header_part.splitlines():
            if b':' in line:
                key, val = line.split(b':', 1)
                key_str = key.decode().strip()
                val_str = val.decode().strip()
                if key_str.lower() == 'status':
                    status_code = int(val_str.split(' ')[0])
                else:
                    headers.append((key_str, val_str))

        self.send_response(status_code)
        for key, val in headers:
            self.send_header(key, val)
        self.end_headers()
        
        self.wfile.write(body)

        if stderr_data:
            print(f"Git Error: {stderr_data.decode('utf-8', errors='replace')}", file=sys.stderr)


print(f"")
print(f"--- Filesystem git HTTP bridge ---")
print(f"Backend: {backend_path}")
print(f"Serving from: {PROJECTS_ROOT}")
print(f"URL: http://localhost:{PORT}/<your-repo-name>")
print(f"----------------------------------")
print(f"")

HTTPServer(('0.0.0.0', PORT), GitRequestHandler).serve_forever()
