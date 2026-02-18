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

        header_part, _, body = stdout_data.partition(b'\r\n\r\n')
        
        self.send_response(200)
        for line in header_part.split(b'\r\n'):
            if b':' in line:
                key, val = line.split(b':', 1)
                self.send_header(key.decode().strip(), val.decode().strip())
        self.end_headers()
        self.wfile.write(body)

        if stderr_data:
            print(f"Git Error: {stderr_data.decode('utf-8', errors='backslashreplace')}", file=sys.stderr)

print(f"")
print(f"--- Filesystem git HTTP bridge ---")
print(f"Backend: {backend_path}")
print(f"Serving from: {PROJECTS_ROOT}")
print(f"URL: http://localhost:{PORT}/<your-repo-name>")
print(f"----------------------------------")
print(f"")

HTTPServer(('0.0.0.0', PORT), GitRequestHandler).serve_forever()
