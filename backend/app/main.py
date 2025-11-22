from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import invoices, purchase_orders, vendors
from app.database import engine, Base

# Create tables (in production, use migrations)
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Accounts Payable Platform API",
    description="API for managing PO-backed invoices",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js default ports
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

