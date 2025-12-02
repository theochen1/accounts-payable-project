from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from app.routers import vendors, documents, agents
from app.database import engine, Base
from app.config import settings
from app.services.storage_service import storage_service
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Log startup information
logger.info("="*60)
logger.info("Starting Accounts Payable Platform API")
logger.info("="*60)
logger.info(f"OpenAI API Key configured: {bool(settings.openai_api_key)}")
logger.info(f"Azure Document Intelligence configured: {bool(settings.azure_doc_intelligence_endpoint and settings.azure_doc_intelligence_key)}")
logger.info(f"OpenAI Model: {settings.openai_model}")
logger.info("="*60)

# Create tables (in production, use migrations)
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Accounts Payable Platform API",
    description="API for managing PO-backed invoices",
    version="1.0.0"
)

# Parse CORS origins from config
def parse_cors_origins(origins_str: str) -> list:
    """Parse CORS origins string into a list, excluding wildcards."""
    origins = []
    for origin in origins_str.split(","):
        origin = origin.strip()
        # Skip wildcard entries (will be handled by allow_origin_regex)
        if "*.vercel.app" not in origin and origin:
            origins.append(origin)
    return origins

# CORS middleware - using allow_origin_regex for Vercel wildcard support
cors_origins = parse_cors_origins(settings.cors_origins)
# Default origins for local development
default_origins = ["http://localhost:3000", "http://localhost:3001"]

# Explicitly add common Vercel domains
vercel_domains = [
    "https://accounts-payable-project.vercel.app",
    "https://accounts-payable-project-git-main-theo-chens-projects.vercel.app",
]

# Combine all origins
all_origins = (cors_origins if cors_origins else default_origins) + vercel_domains

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",  # Allow all Vercel deployments
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(documents.router)  # Unified document queue
app.include_router(vendors.router)
app.include_router(agents.router)  # AI agent exception resolution


@app.get("/")
def root():
    return {"message": "Accounts Payable Platform API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


async def _serve_storage_file(file_path: str):
    """Helper function to serve files from storage"""
    try:
        # Download file from storage (works for both S3 and local)
        file_content = storage_service.download_pdf(file_path)
        
        # Determine content type from file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
        }
        media_type = content_types.get(file_ext, 'application/octet-stream')
        
        # Return file content
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{os.path.basename(file_path)}"'
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")


@app.get("/api/storage/{file_path:path}")
async def serve_storage_file_api(file_path: str):
    """
    Serve files from local storage or S3 (API route)
    
    Args:
        file_path: Storage path (e.g., "invoices/timestamp_filename.pdf")
    """
    return await _serve_storage_file(file_path)


@app.get("/storage/{file_path:path}")
async def serve_storage_file(file_path: str):
    """
    Serve files from local storage or S3 (frontend route)
    
    Args:
        file_path: Storage path (e.g., "invoices/timestamp_filename.pdf")
    """
    return await _serve_storage_file(file_path)


# Exception handler to ensure CORS headers are always sent
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure CORS headers are sent even on errors"""
    logging.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Get the origin from the request
    origin = request.headers.get("origin", "*")
    
    # Check if origin is a Vercel domain or in allowed origins
    is_allowed = (
        origin.endswith(".vercel.app") or
        origin in all_origins or
        any(origin == o for o in default_origins)
    )
    
    cors_origin = origin if is_allowed else "*"
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

