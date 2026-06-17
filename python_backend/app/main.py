# app/main.py
from fastapi import FastAPI
from app.api.routes import router as api_router

app = FastAPI(
    title="Loop Engineering API",
    description="Python microservice for loop engineering auditing, initialization, and cost estimation.",
    version="1.0.0"
)

# Include the API routes with the versioned prefix
app.include_router(api_router)

@app.get("/health")
async def health_check():
    """Endpoint for Docker health checks and system monitoring."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
