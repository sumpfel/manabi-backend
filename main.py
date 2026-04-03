from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import auth, sync, ai, decks, session, units, community

app = FastAPI(title="Nexus Lingua API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(decks.router, prefix="/api/decks", tags=["decks"])
app.include_router(session.router, prefix="/api/session", tags=["session"])
app.include_router(units.router, prefix="/api/units", tags=["units"])
app.include_router(community.router, prefix="/api/community", tags=["community"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Nexus Lingua API is running"}

@app.get("/api/health")
def health_check():
    return {"status": "online"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
