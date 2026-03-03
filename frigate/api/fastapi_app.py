import logging
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from playhouse.sqliteq import SqliteQueueDatabase
from starlette_context import middleware, plugins

from frigate.api import headless
from frigate.comms.event_metadata_updater import EventMetadataPublisher
from frigate.comms.sse import SseEventClient
from frigate.config import FrigateConfig
from frigate.config.camera.updater import CameraConfigUpdatePublisher
from frigate.embeddings import EmbeddingsContext
from frigate.headless.runtime_config import init_runtime_store
from frigate.headless.closed_loop import init_closed_loop_state
from frigate.headless.governance import init_governance_state
from frigate.headless.security import SimpleRateLimiter
from frigate.headless.settings import get_headless_settings
from frigate.ptz.onvif import OnvifController
from frigate.stats.emitter import StatsEmitter
from frigate.storage import StorageMaintainer

logger = logging.getLogger(__name__)


def create_fastapi_app(
    frigate_config: FrigateConfig,
    database: SqliteQueueDatabase,
    embeddings: Optional[EmbeddingsContext],
    detected_frames_processor,
    storage_maintainer: StorageMaintainer,
    onvif: OnvifController,
    stats_emitter: StatsEmitter,
    event_metadata_updater: EventMetadataPublisher,
    config_publisher: CameraConfigUpdatePublisher,
    sse_client: SseEventClient,
    enforce_default_admin: bool = True,
):
    del enforce_default_admin

    logger.info("Starting FastAPI app (headless)")
    headless_settings = get_headless_settings()

    app = FastAPI(
        debug=False,
        swagger_ui_parameters={"apisSorter": "alpha", "operationsSorter": "alpha"},
    )

    if headless_settings.cors_allowlist:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=headless_settings.cors_allowlist,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    app.add_middleware(
        middleware.ContextMiddleware,
        plugins=(plugins.ForwardedForPlugin(),),
    )

    @app.middleware("http")
    async def frigate_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.raw_body = await request.body()

        if database.is_closed():
            database.connect()

        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)

        logger.info(
            "request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request.state.request_id,
            },
        )

        response.headers["x-request-id"] = request.state.request_id

        if not database.is_closed():
            database.close()

        return response

    @app.on_event("startup")
    async def startup():
        logger.info("FastAPI headless started")

    app.frigate_config = frigate_config
    app.embeddings = embeddings
    app.detected_frames_processor = detected_frames_processor
    app.storage_maintainer = storage_maintainer
    app.camera_error_image = None
    app.onvif = onvif
    app.stats_emitter = stats_emitter
    app.event_metadata_updater = event_metadata_updater
    app.config_publisher = config_publisher

    app.state.runtime_config_store = init_runtime_store(frigate_config)
    app.state.headless_settings = headless_settings
    app.state.headless_rate_limiter = SimpleRateLimiter(
        headless_settings.rate_limit_per_minute
    )
    app.state.headless_triggers = {}
    app.state.headless_regions = {}
    app.state.headless_noise_suggestions = {}
    app.state.headless_noise_audit = []
    app.state.headless_closed_loop = init_closed_loop_state()
    app.state.headless_governance = init_governance_state()
    app.state.headless_started_at = time.time()
    app.state.sse_client = sse_client

    app.include_router(headless.ops_router)
    app.include_router(headless.router)

    return app
