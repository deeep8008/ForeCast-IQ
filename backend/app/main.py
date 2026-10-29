"""
ForecastIQ Backend Application Entry Point
FastAPI Multi-Horizon Time-Series Forecasting
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config.settings import settings
from .api.endpoints import router as api_router
from .auth.routes import router as auth_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Universal Time-Series Dataset Engine & Ingestion API for Enterprise Forecasting"
)

# Set up CORS with explicit origins and credentials enabled
cors_origins = list(set(settings.BACKEND_CORS_ORIGINS + [settings.FRONTEND_ORIGIN]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": "Welcome to ForecastIQ Backend Engine",
        "documentation": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
