from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine, upgrade_workflow_schema
from app.models.instrument import Instrument
from app.models.application import Application
from app.models.inspection import Inspection
from app.models.validity_rule import ValidityRule
from app.models.certificate import Certificate
from app.models.user import User
from app.models.measurement_rule import MeasurementRule
from app.routers.instrument import router as instruments_router
from app.routers.application import router as applications_router
from app.routers.inspection import router as inspections_router
from app.routers.certificate import router as certificates_router
from app.routers.validity_rule import router as validity_rules_router
from app.routers.validity import router as validity_router
from app.routers.auth import router as auth_router
from app.routers.measurement_rule import router as measurement_rules_router

app = FastAPI(
    title="SIH26036 Legal Metrology Verification System",
    description="Backend API for instrument verification and certification",
    version="1.0.0",
    debug=settings.DEBUG,
)

# CORS allowlist. In production this is driven exclusively by
# CORS_ALLOWED_ORIGINS; the wildcard only applies to local development.
allowed_origins = settings.CORS_ALLOWED_ORIGINS or (
    [] if settings.IS_PRODUCTION else ["http://localhost:5500", "http://127.0.0.1:5500"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
upgrade_workflow_schema()

app.include_router(instruments_router)
app.include_router(applications_router)
app.include_router(inspections_router)
app.include_router(certificates_router)
app.include_router(validity_rules_router)
app.include_router(validity_router)
app.include_router(auth_router)
app.include_router(measurement_rules_router)
@app.get("/")
def root():
    return {
        "message": "SIH26036 Backend is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }
