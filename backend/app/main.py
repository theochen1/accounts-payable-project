from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers import invoices, purchase_orders, vendors
from app.database import engine, Base
from app.config import settings
import logging
import sys

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
logger.info(f"Clarifai PAT configured: {bool(settings.clarifai_pat)}")
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
app.include_router(invoices.router)
app.include_router(purchase_orders.router)
app.include_router(vendors.router)


@app.get("/")
def root():
    return {"message": "Accounts Payable Platform API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


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

