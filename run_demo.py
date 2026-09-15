import os
import sys

# Forward to server so Render does not crash if run_demo.py is set as start command
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.server import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting Mistri Enterprise API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
