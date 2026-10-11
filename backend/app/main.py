import sys
from pathlib import Path

# Ensure backend directory is in sys.path so 'app' imports always succeed
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import ForecastIQException
from app.api.routes_dataset import router as dataset_router
from app.api.routes_pipeline import router as pipeline_router
from app.api.routes_benchmark import router as benchmark_router
from app.api.routes_forecast import router as forecast_router

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="ForecastIQ AI-Powered Time-Series Forecasting & Evaluation Platform Backend"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register custom exception handler
    @app.exception_handler(ForecastIQException)
    async def forecastiq_exception_handler(request: Request, exc: ForecastIQException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "status_code": exc.status_code
            }
        )

    # Register API Routers
    app.include_router(dataset_router, prefix=settings.API_V1_PREFIX)
    app.include_router(pipeline_router, prefix=settings.API_V1_PREFIX)
    app.include_router(benchmark_router, prefix=settings.API_V1_PREFIX)
    app.include_router(forecast_router, prefix=settings.API_V1_PREFIX)



    @app.get("/", tags=["Health"])
    def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "docs_url": "/docs"
        }

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "healthy"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
