import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from backend.api import app as api_app

# The main app combines the API and serves the frontend root
app = FastAPI(title="Video Generator Runner")

# Mount all the API routes
app.mount("/api", api_app)

# Serve the static files from frontend
from fastapi.staticfiles import StaticFiles
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")

@app.get("/review.html")
def serve_review():
    return FileResponse("frontend/review.html")

if __name__ == "__main__":
    print("🚀 Iniciando Video Generator MVP...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
