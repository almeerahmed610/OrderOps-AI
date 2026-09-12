from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

from app.routes.auth import router as auth_router
from app.routes.customers import router as customers_router
from app.routes.products import router as products_router
from app.routes.orders import router as orders_router
from app.routes.agents import router as agents_router
from app.routes.dashboard import router as dashboard_router


# =========================================================
# APPLICATION
# =========================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "OrderOps AI — Autonomous Order Triage & "
        "Resolution Agent for e-commerce operations."
    ),
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API ROUTES
# =========================================================

# Authentication
app.include_router(
    auth_router,
)

# Customers
app.include_router(
    customers_router,
)

# Products / Inventory
app.include_router(
    products_router,
)

# Orders
app.include_router(
    orders_router,
)

# AI Agents
app.include_router(
    agents_router,
)

# Dashboard
app.include_router(
    dashboard_router,
)


# =========================================================
# API ROOT
# =========================================================

@app.get("/api")
def api_root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "message": "OrderOps AI backend is running.",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "orderops-api",
    }


# =========================================================
# FRONTEND
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[2]

FRONTEND_DIR = BASE_DIR / "frontend"


app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True,
    ),
    name="frontend",
)