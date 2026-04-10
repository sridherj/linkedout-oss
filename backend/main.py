"""Main application entry point for Sample Backend API."""
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from sqlalchemy import create_engine

from shared.utilities.logger import get_logger, set_level, setup_logging
from shared.utilities.request_logging_middleware import RequestLoggingMiddleware
from shared.config import get_config
from shared.infra.db.db_session_manager import DbSessionManager

settings = get_config()
from shared.auth.config import AuthConfig
from shared.auth.dependencies.auth_dependencies import init_auth
from organization.controllers.tenant_controller import tenants_router
from organization.controllers.bu_controller import bus_router
from organization.enrichment_config.controllers.enrichment_config_controller import enrichment_configs_router

# Common agent infrastructure
from common.controllers.agent_run_controller import agent_run_router

# LinkedOut domain
from linkedout.company.controllers.company_controller import companies_router
from linkedout.company_alias.controllers.company_alias_controller import company_aliases_router
from linkedout.crawled_profile.controllers.crawled_profile_controller import crawled_profiles_router
from linkedout.connection.controllers.connection_controller import connections_router
from linkedout.role_alias.controllers.role_alias_controller import role_aliases_router
from linkedout.experience.controllers.experience_controller import experiences_router
from linkedout.education.controllers.education_controller import educations_router
from linkedout.profile_skill.controllers.profile_skill_controller import profile_skills_router
from linkedout.import_job.controllers.import_job_controller import import_jobs_router
from linkedout.enrichment_event.controllers.enrichment_event_controller import enrichment_events_router
from linkedout.search_session.controllers.search_session_controller import search_sessions_router
from linkedout.search_session.controllers.search_turn_controller import search_turns_router
from linkedout.search_tag.controllers.search_tag_controller import search_tags_router
from linkedout.contact_source.controllers.contact_source_controller import contact_sources_router
from linkedout.import_pipeline.controller import import_pipeline_router
from linkedout.enrichment_pipeline.controller import enrichment_pipeline_router
from linkedout.intelligence.controllers.search_controller import search_router
from linkedout.intelligence.controllers.best_hop_controller import best_hop_router

# Dashboard (read-only aggregation, not CRUD)
from linkedout.dashboard.controller import dashboard_router

# Funding / startup pipeline domain
from linkedout.funding.controllers.funding_round_controller import funding_rounds_router
from linkedout.funding.controllers.growth_signal_controller import growth_signals_router
from linkedout.funding.controllers.startup_tracking_controller import startup_trackings_router


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.

    Handles startup and shutdown logic.
    """
    # Startup
    setup_logging(
        environment=settings.environment,
        log_level=settings.log_level,
    )
    logger.info('Starting LinkedOut API...')
    logger.info(f'Environment: {settings.environment}')
    logger.info(f'Database: {settings.database_url}')

    # Create DbSessionManager and store on app.state
    # Skip if tests pre-set db_manager (integration tests do this)
    if not hasattr(app.state, 'db_manager'):
        engine = create_engine(settings.database_url, echo=settings.db_echo_log)
        app.state.db_manager = DbSessionManager(engine)
        app.state._owns_engine = True
    else:
        app.state._owns_engine = False

    # Initialize auth
    auth_config = AuthConfig()
    init_auth(auth_config)
    if auth_config.FIREBASE_ENABLED and auth_config.FIREBASE_CREDENTIALS_PATH:
        from shared.auth.providers.firebase_auth_provider import initialize_firebase_global
        initialize_firebase_global(auth_config)
    logger.info(f'Auth enabled: {auth_config.AUTH_ENABLED}')

    yield

    # Shutdown — dispose engine if lifespan created it
    if app.state._owns_engine:
        app.state.db_manager._engine.dispose()
    logger.info('Shutting down LinkedOut API...')


# Create FastAPI application
app = FastAPI(
    title='LinkedOut API',
    description='''
    Professional network intelligence tool — FastAPI backend.

    - **MVCS Architecture** (Model-View-Controller-Service)
    - **Multi-tenancy** with tenant and business unit support
    - **Repository Pattern** for data access
    - **Pydantic V2** for validation
    - **SQLAlchemy** ORM with PostgreSQL
    - **Alembic** for database migrations
    ''',
    version='1.0.0',
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(',') if settings.cors_origins else ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Register routers
app.include_router(tenants_router)
app.include_router(bus_router)
app.include_router(enrichment_configs_router)

# Common agent infrastructure
app.include_router(agent_run_router)

# LinkedOut domain
app.include_router(companies_router)
app.include_router(company_aliases_router)
app.include_router(crawled_profiles_router)
app.include_router(connections_router)
app.include_router(role_aliases_router)
app.include_router(experiences_router)
app.include_router(educations_router)
app.include_router(profile_skills_router)
app.include_router(import_jobs_router)
app.include_router(enrichment_events_router)
app.include_router(search_sessions_router)
app.include_router(search_turns_router)
app.include_router(search_tags_router)
app.include_router(contact_sources_router)
app.include_router(import_pipeline_router)
app.include_router(enrichment_pipeline_router)

# Intelligence / search
app.include_router(search_router)
app.include_router(best_hop_router)

# Dashboard (read-only aggregation, not CRUD)
app.include_router(dashboard_router)

# Funding / startup pipeline domain
app.include_router(funding_rounds_router)
app.include_router(growth_signals_router)
app.include_router(startup_trackings_router)

@app.get('/')
async def root():
    """Root endpoint with API information."""
    return {
        'name': 'LinkedOut API',
        'version': '1.0.0',
        'environment': settings.environment,
        'docs': '/docs',
        'openapi': '/openapi.json'
    }

@app.get('/health')
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'ok',
        'environment': settings.environment
    }


if __name__ == '__main__':
    # Run the application
    uvicorn.run(
        'main:app',
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False
    )
