"""
Punto de entrada de la aplicación FastAPI.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.logging_config import setup_logging
from app.database.connection import init_db, close_db
from app.api.routes import documents, rag, knowledge
from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor del ciclo de vida de la aplicación.
    """
    # Inicio
    logger.info("Iniciando aplicación...")
    setup_logging()
    
    # Inicializar base de datos
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"No se pudo inicializar la base de datos: {e}")
    
    yield
    
    # Cierre
    logger.info("Cerrando aplicación...")
    await close_db()


def create_app() -> FastAPI:
    """
    Crea y configura la aplicación FastAPI.
    """
    settings = get_settings()
    
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Configurar rate limiter
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    
    # Manejador de errores de rate limiting
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Demasiadas solicitudes. Por favor, intente más tarde.",
                "error": "rate_limit_exceeded"
            }
        )
    
    # CORS configurado de forma segura
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        max_age=600,  # Cache preflight por 10 minutos
    )
    
    # Middleware para manejo de errores global
    @app.middleware("http")
    async def error_handling_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Error no manejado: {str(e)}")
            
            # En producción, no revelar detalles del error
            if settings.debug:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": "Error interno del servidor",
                        "error": str(e)
                    }
                )
            else:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": "Error interno del servidor",
                        "error": "contacte al administrador"
                    }
                )
    
    # Middleware de logging de requests
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        logger.info(f"{request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(f"{request.method} {request.url.path} - {response.status_code}")
        return response
    
    # Incluir routers
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    
    # Health check
    @app.get("/health", tags=["Sistema"])
    async def health_check():
        """Endpoint de verificación de salud."""
        return {
            "status": "healthy",
            "version": settings.api_version,
        }
    
    return app


# Instancia de la aplicación
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
