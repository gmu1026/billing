from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alibaba, hb, master
from app.config import settings
from app.database import Base, engine

# Import models to register them with SQLAlchemy
from app.models import alibaba as alibaba_models  # noqa: F401
from app.models import hb as hb_models  # noqa: F401


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


@app.get("/")
def root():
    return {"message": "Billing Slip Automation API", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
