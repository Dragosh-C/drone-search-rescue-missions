import http.server
import socketserver
import os

PORT = 8000

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')
IMAGE_DIR = "/ros2_ws/captured_targets"

class UnifiedHandler(http.server.SimpleHTTPRequestHandler):
    
    def translate_path(self, path):
        if path.endswith('.jpg'):
            filename = os.path.basename(path)
            return os.path.join(IMAGE_DIR, filename)
        
        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

with socketserver.TCPServer(("", PORT), UnifiedHandler) as httpd:
    print(f"GCS Dashboard & Evidence Server Running!")
    print(f"Port: {PORT}")
    print(f"Frontend: {FRONTEND_DIR}")
    print(f"Images: {IMAGE_DIR}")
    httpd.serve_forever()