from __future__ import annotations

from typing import Any


def _bool_env(name: str, env: dict[str, str]) -> bool:
    value = str(env.get(name, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _phase(
    *,
    phase_id: str,
    title: str,
    passed: bool,
    blockers: list[str],
    evidence: list[str],
) -> dict[str, Any]:
    if passed:
        status = "passed"
    elif evidence:
        status = "in_progress"
    else:
        status = "failed"

    return {
        "phase_id": phase_id,
        "title": title,
        "status": status,
        "passed": passed,
        "blockers": blockers,
        "evidence": evidence,
    }


def build_production_readiness_report(context: dict[str, Any]) -> dict[str, Any]:
    env = context.get("env", {})
    settings = context.get("settings", {})
    readiness = context.get("readiness", {})
    release_gate = context.get("release_gate", {})
    migrations = context.get("migrations", {})
    secrets = context.get("secrets", {})
    delivery = context.get("delivery", {})
    storage_sync = context.get("storage_sync", {})
    dr = context.get("dr", {})
    backups = context.get("backups", [])
    optimization_gate = context.get("optimization_gate", {})
    runbooks = context.get("runbooks", {})
    governance = context.get("governance", {})
    load_chaos_summary = context.get("load_chaos_summary", {})
    scaling_state = context.get("scaling_state", {})
    rate_limiter = context.get("rate_limiter", {})
    redis_enabled = bool(context.get("redis_enabled", False))
    supply_chain = context.get("supply_chain", {})

    phase_items: list[dict[str, Any]] = []

    # 00
    owner = str(governance.get("owner", "")).strip().lower()
    committee = governance.get("technical_committee", [])
    p00_blockers: list[str] = []
    p00_evidence: list[str] = []
    if owner and owner != "unassigned":
        p00_evidence.append("owner_defined")
    else:
        p00_blockers.append("missing_readiness_owner")
    if isinstance(committee, list) and committee:
        p00_evidence.append("technical_committee_defined")
    else:
        p00_blockers.append("missing_technical_committee")
    phase_items.append(
        _phase(
            phase_id="00",
            title="Baseline e Gap Analysis",
            passed=len(p00_blockers) == 0,
            blockers=p00_blockers,
            evidence=p00_evidence,
        )
    )

    # 01
    p01_blockers: list[str] = []
    p01_evidence: list[str] = []
    if bool(settings.get("enabled", False)):
        p01_evidence.append("headless_enabled")
    else:
        p01_blockers.append("headless_not_enabled")
    if str(settings.get("auth_mode", "")) in {"hmac", "jwt"}:
        p01_evidence.append("auth_mode_valid")
    else:
        p01_blockers.append("invalid_auth_mode")
    db_driver = str(env.get("FRIGATE_DB_DRIVER", "sqlite")).strip().lower()
    if db_driver in {"sqlite", "mysql", "postgres", "postgresql"}:
        p01_evidence.append(f"db_driver:{db_driver}")
    else:
        p01_blockers.append("unsupported_db_driver")
    phase_items.append(
        _phase(
            phase_id="01",
            title="Paridade de Ambiente e Dependencias",
            passed=len(p01_blockers) == 0,
            blockers=p01_blockers,
            evidence=p01_evidence,
        )
    )

    # 02
    p02_blockers: list[str] = []
    p02_evidence: list[str] = []
    if bool(release_gate.get("passed", False)):
        p02_evidence.append("release_gate_passed")
    else:
        p02_blockers.append("release_gate_failed")
    if _bool_env("FRIGATE_CI_QUALITY_GATES_ENABLED", env):
        p02_evidence.append("ci_quality_gates_enabled")
    else:
        p02_blockers.append("ci_quality_gates_disabled")
    phase_items.append(
        _phase(
            phase_id="02",
            title="Matriz de Testes e Gates de Qualidade",
            passed=len(p02_blockers) == 0,
            blockers=p02_blockers,
            evidence=p02_evidence,
        )
    )

    # 03
    p03_blockers: list[str] = []
    p03_evidence: list[str] = []
    auth_mode = str(settings.get("auth_mode", ""))
    if auth_mode == "hmac":
        if env.get("FRIGATE_API_HMAC_KEYS_JSON"):
            p03_evidence.append("hmac_keys_configured")
        else:
            p03_blockers.append("missing_hmac_keys")
    elif auth_mode == "jwt":
        if env.get("FRIGATE_API_JWT_SECRET"):
            p03_evidence.append("jwt_secret_configured")
        else:
            p03_blockers.append("missing_jwt_secret")

    secret_history = secrets.get("history", []) if isinstance(secrets, dict) else []
    if isinstance(secret_history, list) and secret_history:
        p03_evidence.append("secrets_rotation_history")
    else:
        p03_blockers.append("secrets_rotation_not_exercised")

    phase_items.append(
        _phase(
            phase_id="03",
            title="Hardening de Seguranca e Segredos",
            passed=len(p03_blockers) == 0,
            blockers=p03_blockers,
            evidence=p03_evidence,
        )
    )

    # 04
    p04_blockers: list[str] = []
    p04_evidence: list[str] = []
    schema_version = int(migrations.get("schema_version", 0) or 0)
    migration_history = migrations.get("history", []) if isinstance(migrations, dict) else []
    if schema_version >= 1:
        p04_evidence.append(f"schema_version:{schema_version}")
    else:
        p04_blockers.append("invalid_schema_version")
    if isinstance(migration_history, list) and migration_history:
        p04_evidence.append("migration_history_present")
    else:
        p04_blockers.append("migrations_not_exercised")
    if isinstance(backups, list) and backups:
        p04_evidence.append("backup_available")
    else:
        p04_blockers.append("backup_missing")
    phase_items.append(
        _phase(
            phase_id="04",
            title="Hardening de Dados e Migracoes",
            passed=len(p04_blockers) == 0,
            blockers=p04_blockers,
            evidence=p04_evidence,
        )
    )

    # 05
    p05_blockers: list[str] = []
    p05_evidence: list[str] = []
    if bool(rate_limiter.get("configured", False)):
        p05_evidence.append("rate_limiter_configured")
    else:
        p05_blockers.append("rate_limiter_not_configured")
    if redis_enabled:
        p05_evidence.append("distributed_state_backend_enabled")
    else:
        p05_blockers.append("redis_distributed_state_disabled")
    phase_items.append(
        _phase(
            phase_id="05",
            title="Estado Distribuido e Controle de Abuso",
            passed=len(p05_blockers) == 0,
            blockers=p05_blockers,
            evidence=p05_evidence,
        )
    )

    # 06
    p06_blockers: list[str] = []
    p06_evidence: list[str] = []
    channels = delivery.get("channels", {}) if isinstance(delivery, dict) else {}
    dead_letters = delivery.get("dead_letters", []) if isinstance(delivery, dict) else []
    pending_total = int(delivery.get("pending_total", 0) or 0)
    if isinstance(channels, dict) and channels:
        p06_evidence.append("delivery_channels_active")
    else:
        p06_blockers.append("delivery_channels_inactive")
    if isinstance(dead_letters, list) and len(dead_letters) == 0:
        p06_evidence.append("dlq_empty")
    else:
        p06_blockers.append("dlq_has_items")
    if pending_total <= 5000:
        p06_evidence.append("pending_total_within_limit")
    else:
        p06_blockers.append("pending_total_above_limit")
    phase_items.append(
        _phase(
            phase_id="06",
            title="Entrega de Eventos e Backpressure",
            passed=len(p06_blockers) == 0,
            blockers=p06_blockers,
            evidence=p06_evidence,
        )
    )

    # 07
    p07_blockers: list[str] = []
    p07_evidence: list[str] = []
    if bool(release_gate.get("passed", False)):
        p07_evidence.append("slo_release_gate_ok")
    else:
        p07_blockers.append("slo_release_gate_failed")
    throughput = int(storage_sync.get("throughput", 0) or 0)
    if throughput > 0:
        p07_evidence.append("storage_sync_throughput_present")
    else:
        p07_blockers.append("storage_sync_throughput_zero")
    phase_items.append(
        _phase(
            phase_id="07",
            title="Observabilidade, SLO e Alertas",
            passed=len(p07_blockers) == 0,
            blockers=p07_blockers,
            evidence=p07_evidence,
        )
    )

    # 08
    p08_blockers: list[str] = []
    p08_evidence: list[str] = []
    if bool(optimization_gate.get("passed", False)):
        p08_evidence.append("optimization_benchmark_gate_passed")
    else:
        p08_blockers.append("optimization_benchmark_gate_failed")

    if bool(load_chaos_summary.get("gate_passed", False)):
        p08_evidence.append("load_chaos_gate_passed")
    else:
        p08_blockers.append("load_chaos_gate_failed")

    phase_items.append(
        _phase(
            phase_id="08",
            title="Performance e Capacidade",
            passed=len(p08_blockers) == 0,
            blockers=p08_blockers,
            evidence=p08_evidence,
        )
    )

    # 09
    p09_blockers: list[str] = []
    p09_evidence: list[str] = []
    exercises = dr.get("exercises", []) if isinstance(dr, dict) else []
    successful_exercises = [x for x in exercises if bool(x.get("success", False))]
    if isinstance(backups, list) and backups:
        p09_evidence.append("backup_exists")
    else:
        p09_blockers.append("backup_not_executed")
    if successful_exercises:
        p09_evidence.append("dr_exercise_successful")
    else:
        p09_blockers.append("dr_exercise_missing_or_failed")
    phase_items.append(
        _phase(
            phase_id="09",
            title="Disaster Recovery e Backup/Restore",
            passed=len(p09_blockers) == 0,
            blockers=p09_blockers,
            evidence=p09_evidence,
        )
    )

    # 10
    p10_blockers: list[str] = []
    p10_evidence: list[str] = []
    rollout = scaling_state.get("rollout", {}) if isinstance(scaling_state, dict) else {}
    history = rollout.get("history", []) if isinstance(rollout, dict) else []
    if isinstance(history, list) and history:
        p10_evidence.append("rollout_history_present")
    else:
        p10_blockers.append("rollout_history_missing")
    if bool(context.get("contract_compatibility_checked", False)):
        p10_evidence.append("contract_compatibility_checked")
    else:
        p10_blockers.append("contract_compatibility_not_checked")
    phase_items.append(
        _phase(
            phase_id="10",
            title="Rollout de Release e Gestao de Mudanca",
            passed=len(p10_blockers) == 0,
            blockers=p10_blockers,
            evidence=p10_evidence,
        )
    )

    # 11
    p11_blockers: list[str] = []
    p11_evidence: list[str] = []
    if isinstance(runbooks, dict) and len(runbooks) >= 3:
        p11_evidence.append("runbooks_available")
    else:
        p11_blockers.append("runbooks_incomplete")
    if bool(context.get("oncall_drill_completed", False)):
        p11_evidence.append("oncall_drill_completed")
    else:
        p11_blockers.append("oncall_drill_not_recorded")
    phase_items.append(
        _phase(
            phase_id="11",
            title="Runbooks e Prontidao de On-call",
            passed=len(p11_blockers) == 0,
            blockers=p11_blockers,
            evidence=p11_evidence,
        )
    )

    # 12
    p12_blockers: list[str] = []
    p12_evidence: list[str] = []
    if bool(readiness.get("ready", False)):
        p12_evidence.append("runtime_ready")
    else:
        p12_blockers.append("runtime_not_ready")
    if bool(release_gate.get("passed", False)):
        p12_evidence.append("release_gate_passed")
    else:
        p12_blockers.append("release_gate_not_passed")
    phase_items.append(
        _phase(
            phase_id="12",
            title="Go-live e Hypercare",
            passed=len(p12_blockers) == 0,
            blockers=p12_blockers,
            evidence=p12_evidence,
        )
    )

    # 13
    p13_blockers: list[str] = []
    p13_evidence: list[str] = []
    weekly_reports = (
        context.get("optimization", {})
        .get("playbook", {})
        .get("weekly_reports", [])
        if isinstance(context.get("optimization", {}), dict)
        else []
    )
    audit_entries = governance.get("audit_entries", []) if isinstance(governance, dict) else []
    if isinstance(weekly_reports, list) and weekly_reports:
        p13_evidence.append("weekly_reports_present")
    else:
        p13_blockers.append("weekly_reports_missing")
    if isinstance(audit_entries, list) and audit_entries:
        p13_evidence.append("governance_audit_present")
    else:
        p13_blockers.append("governance_audit_missing")
    if not bool(supply_chain.get("release_blocked", False)):
        p13_evidence.append("supply_chain_not_blocking")
    else:
        p13_blockers.append("supply_chain_release_blocked")

    phase_items.append(
        _phase(
            phase_id="13",
            title="Pos Go-live e Governanca Continua",
            passed=len(p13_blockers) == 0,
            blockers=p13_blockers,
            evidence=p13_evidence,
        )
    )

    total = len(phase_items)
    passed = len([item for item in phase_items if item.get("passed")])
    in_progress = len([item for item in phase_items if item.get("status") == "in_progress"])
    failed = len([item for item in phase_items if item.get("status") == "failed"])

    production_ready = passed == total and bool(readiness.get("ready", False)) and bool(
        release_gate.get("passed", False)
    )

    return {
        "summary": {
            "total_phases": total,
            "passed": passed,
            "in_progress": in_progress,
            "failed": failed,
            "score_pct": round((passed / total) * 100, 1) if total else 0.0,
            "production_ready": production_ready,
        },
        "pending_phase_ids": [
            item["phase_id"] for item in phase_items if item.get("status") != "passed"
        ],
        "phases": phase_items,
    }
