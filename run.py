"""
SetuHaul Logistics — Root Backend Launcher
Runs the backend on port 8000 with reload enabled.
"""
import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
os.chdir(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Starting SetuHaul Backend on http://{host}:{port}")
    uvicorn.run("app.api.main:app", host=host, port=port, reload=True)
