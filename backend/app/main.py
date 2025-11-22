from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import invoices, purchase_orders, vendors
from app.database import engine, Base
from app.config import settings

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["http://localhost:3000", "http://localhost:3001"],
    allow_origin_regex=r"https://.*\.vercel\.app$",  # Allow all Vercel deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

