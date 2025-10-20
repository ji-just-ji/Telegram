from flask import Flask, send_from_directory
import os
import string
import random
from pyngrok import ngrok

SERVER_PORT = 8000
SERVER_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
AUTH_TOKEN = os.getenv("ngrok_AUTHTOKEN")
file_map = {}

def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
  
  
app = Flask(__name__)
@app.route('/videos/<file_id>')
def get_video(file_id):
    # Lookup the actual filename
    filename = file_map.get(file_id)
    
    # Build full path
    path = os.path.join(SERVER_DIR, filename) if filename else None

    # DEBUG LINES
    print("===== DEBUG GET VIDEO =====")
    print("Requested file_id:", file_id)
    print("Mapped filename:", filename)
    print("Full path:", path)
    print("File exists:", os.path.exists(path) if path else False)
    print("===========================")

    # Return file or 404
    if not filename or not os.path.exists(path): # type: ignore
        return "File not found", 404
    return send_from_directory(SERVER_DIR, filename, as_attachment=True)

def register_file(filename):
    """Register a filename and get a safe URL ID."""
    file_id = generate_id()
    file_map[file_id] = filename
    return file_id
    
def start_server():
    # Start ngrok tunnel
    public_url = ngrok.connect(SERVER_PORT) # type: ignore
    print(f" * ngrok tunnel available at: {public_url}/videos/<filename>")
    app.run(port=SERVER_PORT)