"""
SetuHaul Logistics — Quick Backend Runner
Runs uvicorn on port 8000 with hot-reload enabled.
"""
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Starting SetuHaul Logistics Backend on http://{host}:{port}")
    uvicorn.run("app.api.main:app", host=host, port=port, reload=True)
