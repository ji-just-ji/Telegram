from flask import Flask, send_file
import os
import string
import random
from pyngrok import ngrok
import threading

SERVER_PORT = 8000
SERVER_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
AUTH_TOKEN = os.getenv("ngrok_AUTHTOKEN")
file_map = {}
server_started = False

def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

app = Flask(__name__)

@app.route('/videos/<file_id>')
def get_video(file_id):
    full_path = file_map.get(file_id)
    if not full_path or not os.path.exists(full_path):
        print(f"❌ 404: file_id={file_id}, path={full_path}")
        return "File not found", 404

    # DEBUG
    print(f"✅ Serving {full_path} for id {file_id}")
    return send_file(full_path, as_attachment=True)

def register_file(full_path: str):
    """Register a full file path and return a URL-safe ID."""
    # full_path is already the correct path
    
    # Make absolute path relative to current working directory
    abs_path = os.path.abspath(full_path) # Changed 'normalized_path' to 'full_path'

    # Verify file exists
    if not os.path.exists(abs_path):
        print(f"❌ File does not exist: {abs_path}")
        raise FileNotFoundError(abs_path)

    file_id = generate_id()
    print(f"🔖 Registering file: id={file_id}, path={abs_path}")
    file_map[file_id] = abs_path
    return file_id



def start_server():
    """Start Flask server and ngrok tunnel in a background thread."""
    global server_started
    if server_started:
        return
    server_started = True

    # Start ngrok tunnel
    public_url = ngrok.connect(SERVER_PORT)  # type: ignore
    print(f"🌍 ngrok tunnel: {public_url}/videos/<file_id>")

    # Run Flask app in a background thread
    def run_app():
        app.run(host="0.0.0.0", port=SERVER_PORT, threaded=True)

    thread = threading.Thread(target=run_app, daemon=True)
    thread.start()
