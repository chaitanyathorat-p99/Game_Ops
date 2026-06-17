from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
import os

app = FastAPI(
    title="Game Ops Operations Center",
    description="Backend service and web dashboard to monitor game lobby metrics, leaderboards, anti-cheat status, and matchmaking.",
    version="1.0.0"
)

# CORS middleware for local frontend dev flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core api routes
app.include_router(api_router, prefix="/api")

# Ensure static folder exists
os.makedirs("static", exist_ok=True)

# Serve dashboard at root
@app.get("/")
def read_index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Game Ops API is running. Please upload dashboard files to static/ to view UI."}

# Mount static assets directory
app.mount("/static", StaticFiles(directory="static"), name="static")
