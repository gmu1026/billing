from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    additional_charge,
    alibaba,
    billing_profile,
    contract_billing_profile,
    file_import,
    hb,
    master,
    pro_rata,
    slip,
    slip_template,
    split_billing,
)
from app.config import settings
from app.database import Base, engine

# Import models to register them with SQLAlchemy
from app.models import alibaba as alibaba_models  # noqa: F401
from app.models import billing_profile as billing_profile_models  # noqa: F401
from app.models import hb as hb_models  # noqa: F401
from app.models import slip as slip_models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(alibaba.router)
app.include_router(master.router)
app.include_router(hb.router)
app.include_router(slip.router)
app.include_router(file_import.router)
app.include_router(billing_profile.router)
app.include_router(contract_billing_profile.router)
app.include_router(additional_charge.router)
app.include_router(pro_rata.router)
app.include_router(split_billing.router)
app.include_router(slip_template.router)


@app.get("/")
def root():
    return {"message": "Billing Slip Automation API", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
