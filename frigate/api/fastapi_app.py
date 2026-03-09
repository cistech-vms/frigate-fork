import logging
import os
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
from frigate.headless.db_adapter import build_database_adapter
from frigate.headless.disaster_recovery import DisasterRecoveryPlan
from frigate.headless.governance import init_governance_state
from frigate.headless.horizontal_scaling import HorizontalScalingManager
from frigate.headless.idempotency import IdempotencyStore
from frigate.headless.load_chaos_validation import LoadChaosValidator
from frigate.headless.migrations import MigrationManager
from frigate.headless.object_storage import build_object_storage_adapter
from frigate.headless.optimization_engine import OptimizationEngine
from frigate.headless.adaptive_tuning import AdaptiveTuningManager
from frigate.headless.readiness import evaluate_readiness
from frigate.headless.rate_limit import DistributedRateLimiter
from frigate.headless.redis_adapter import build_redis_adapter
from frigate.headless.reliable_delivery import ReliableEventDelivery
from frigate.headless.runbooks import default_runbooks
from frigate.headless.secrets_rotation import SecretRotationManager
from frigate.headless.self_healing import init_self_healing_state
from frigate.headless.state_persistence import get_headless_state_store
from frigate.headless.storage_sync import StorageSyncManager
from frigate.headless.supply_chain import SupplyChainHardening
from frigate.headless.tenant_isolation import TenantQuotaManager
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
        app.state.reliable_delivery.start()
        app.state.storage_sync.start()

    @app.on_event("shutdown")
    async def shutdown():
        app.state.reliable_delivery.stop()
        app.state.storage_sync.stop()

    app.frigate_config = frigate_config
    app.database = database
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
    app.state.headless_state_store = get_headless_state_store()
    app.state.headless_db_adapter = build_database_adapter()
    app.state.headless_redis_adapter = build_redis_adapter()
    app.state.headless_object_storage = build_object_storage_adapter()
    app.state.headless_secret_rotation = SecretRotationManager()
    app.state.headless_migrations = MigrationManager()
    app.state.headless_idempotency = IdempotencyStore()
    app.state.headless_runbooks = default_runbooks()
    app.state.headless_dr = DisasterRecoveryPlan()
    app.state.headless_quotas = TenantQuotaManager()
    app.state.headless_supply_chain = SupplyChainHardening()
    app.state.headless_load_chaos = LoadChaosValidator()
    app.state.headless_horizontal_scaling = HorizontalScalingManager(
        node_id=os.getenv("FRIGATE_NODE_ID", "node-1")
    )
    app.state.headless_optimization = OptimizationEngine()
    app.state.headless_adaptive_tuning = AdaptiveTuningManager()
    app.state.headless_rate_limiter = DistributedRateLimiter(
        limit_per_minute=headless_settings.rate_limit_per_minute,
        block_base_sec=headless_settings.rate_limit_block_base_sec,
        block_max_sec=headless_settings.rate_limit_block_max_sec,
        state_path=os.getenv(
            "FRIGATE_RATE_LIMIT_STATE_PATH", "/config/headless_rate_limit.json"
        ),
        redis_adapter=app.state.headless_redis_adapter,
    )
    app.state.headless_security_audit = []
    persisted_state = app.state.headless_state_store.load()
    app.state.headless_triggers = persisted_state.get("triggers", {})
    app.state.headless_regions = persisted_state.get("regions", {})
    selected_tenant, runtime_overlay = app.state.headless_state_store.choose_runtime_overlay(
        headless_settings.tenant_id
    )
    app.state.headless_runtime_tenant = selected_tenant
    if runtime_overlay:
        try:
            app.state.runtime_config_store.replace_runtime_overlay(runtime_overlay)
        except Exception:
            logger.exception("Failed to restore persisted runtime overlay; starting with empty overlay")
    app.state.headless_noise_suggestions = {}
    app.state.headless_noise_audit = []
    app.state.headless_closed_loop = init_closed_loop_state()
    app.state.headless_self_healing = init_self_healing_state()
    app.state.headless_governance = init_governance_state()
    app.state.headless_started_at = time.time()
    app.state.sse_client = sse_client
    app.state.storage_sync = StorageSyncManager(
        state_store=app.state.headless_state_store,
        object_storage=app.state.headless_object_storage,
    )
    app.state.reliable_delivery = ReliableEventDelivery(
        sse_client=sse_client,
        state_store=app.state.headless_state_store,
        storage_sync_manager=app.state.storage_sync,
        webhook_url=os.getenv("FRIGATE_HEADLESS_EVENTS_WEBHOOK_URL"),
        max_attempts=int(os.getenv("FRIGATE_EVENT_DELIVERY_MAX_ATTEMPTS", "5")),
        backoff_base_sec=float(os.getenv("FRIGATE_EVENT_DELIVERY_BACKOFF_BASE_SEC", "1.0")),
        backoff_max_sec=float(os.getenv("FRIGATE_EVENT_DELIVERY_BACKOFF_MAX_SEC", "30.0")),
        jitter_ratio=float(os.getenv("FRIGATE_EVENT_DELIVERY_JITTER_RATIO", "0.2")),
    )
    app.state.headless_readiness = evaluate_readiness(
        stats=stats_emitter.get_latest_stats(),
        db_connected=not database.is_closed(),
        sse_health=sse_client.stream_health(),
        canary_status={"status": "idle"},
        started_at=app.state.headless_started_at,
        warmup_sec=headless_settings.readiness_warmup_sec,
        min_process_fps=headless_settings.readiness_min_process_fps,
        max_skipped_process_ratio=headless_settings.readiness_max_skipped_process_ratio,
        max_sse_fill_ratio=headless_settings.readiness_max_sse_fill_ratio,
    )

    app.include_router(headless.ops_router)
    app.include_router(headless.router)

    return app
