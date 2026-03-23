# backend/main.py — correct order

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from engines.ml_engine import ml_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Loading ML models...")
    ml_engine.load_models()
    print("✅ Models loaded. Server ready!")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title="AI Identity Risk Score Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# ═══════════════════════════════════════
# CORS — MUST BE BEFORE ROUTERS
# ═══════════════════════════════════════
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════
# ROUTERS — AFTER CORS
# ═══════════════════════════════════════
from routers.tenant import router as tenant_router
from routers.evaluate import router as evaluate_router
from routers.dashboard import router as dashboard_router
from routers.usage import router as usage_router
from routers.webhook import router as webhook_router

app.include_router(tenant_router)
app.include_router(evaluate_router)
app.include_router(dashboard_router)
app.include_router(usage_router)
app.include_router(webhook_router)


@app.get("/", tags=["Health"])
async def root():
    return {"service": "AI Identity Risk Score Engine", "status": "healthy"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "models_loaded": ml_engine._loaded}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)