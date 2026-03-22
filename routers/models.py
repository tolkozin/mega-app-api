"""Model execution endpoints — subscription, e-commerce, and SaaS."""

import math
import signal
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from core.model_config import ModelConfig
from core.engine import run_model
from core.scenarios import build_scenario_params

from ecommerce.model_config import EcomConfig
from ecommerce.engine import run_ecom_model
from ecommerce.scenarios import build_ecom_scenario_params

from saas.model_config import SaasConfig
from saas.engine import run_saas_model
from saas.scenarios import build_saas_scenario_params

logger = logging.getLogger("revenuemap.models")

router = APIRouter(prefix="/api/run", tags=["models"])

# --------------- constants ---------------

MAX_TOTAL_MONTHS = 240
MAX_MC_ITERATIONS = 500
MODEL_TIMEOUT_SECONDS = 30


# --------------- helpers ---------------

def sanitize(obj: Any, depth: int = 0) -> Any:
    """Replace NaN/Infinity floats with None for JSON serialization."""
    if depth > 20:
        return obj
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(i, depth + 1) for i in obj]
    return obj


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Model computation timed out")


def run_with_timeout(fn, *args, timeout_sec: int = MODEL_TIMEOUT_SECONDS):
    """Run a function with a timeout. Falls back to no-timeout on Windows."""
    try:
        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_sec)
        try:
            return fn(*args)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    except (AttributeError, ValueError):
        # Windows (no SIGALRM) or non-main thread — run without timeout
        return fn(*args)


def _safe_num(val: Any, default: float = 0) -> float:
    """Convert a value to a finite number, falling back to default."""
    if val is None or val == "":
        return default
    try:
        n = float(val)
        if math.isnan(n) or math.isinf(n):
            return default
        return n
    except (TypeError, ValueError):
        return default


def validate_config_dict(config: dict) -> dict:
    """Clamp dangerous values and sanitise inputs before parsing."""
    config = config.copy()

    # Sanitise all numeric values (handles "", None, NaN)
    for key, val in config.items():
        if isinstance(val, dict):
            # Phase sub-configs — sanitise recursively
            config[key] = {k: _safe_num(v) if not isinstance(v, dict) else v
                           for k, v in val.items()}
        elif key != "type" and not isinstance(val, (dict, list, bool)):
            config[key] = _safe_num(val)

    if "total_months" in config:
        config["total_months"] = max(1, min(int(config["total_months"]), MAX_TOTAL_MONTHS))
    if "mc_iterations" in config:
        config["mc_iterations"] = max(1, min(int(config["mc_iterations"]), MAX_MC_ITERATIONS))

    # Phase durations must be >= 1
    if "phase1_dur" in config:
        config["phase1_dur"] = max(1, int(config["phase1_dur"]))
    if "phase2_dur" in config:
        config["phase2_dur"] = max(1, int(config["phase2_dur"]))

    # Ensure phases fit within total months
    total = config.get("total_months", 60)
    p1 = config.get("phase1_dur", 3)
    p2 = config.get("phase2_dur", 3)
    if p1 + p2 >= total:
        config["phase1_dur"] = max(1, total // 3)
        config["phase2_dur"] = max(1, total // 3)

    return config


# --------------- request schemas ---------------

class SubscriptionRunRequest(BaseModel):
    config: dict
    sensitivity: dict | None = None


class EcommerceRunRequest(BaseModel):
    config: dict
    sensitivity: dict | None = None


class SaasRunRequest(BaseModel):
    config: dict
    sensitivity: dict | None = None


# --------------- endpoints ---------------

@router.post("/subscription")
def run_subscription(req: SubscriptionRunRequest):
    validated = validate_config_dict(req.config)
    try:
        config = ModelConfig.from_dict(validated)
    except Exception as e:
        logger.warning("Invalid subscription config: %s", e)
        raise HTTPException(status_code=422, detail="Invalid configuration")

    sens = req.sensitivity if req.sensitivity is not None else build_scenario_params(config)["base"]

    try:
        logger.info("Running subscription model: %d months", config.total_months)
        df, milestones, retention_matrix = run_with_timeout(run_model, config, sens)
    except TimeoutError:
        logger.error("Subscription model timed out (%d months)", config.total_months)
        raise HTTPException(status_code=504, detail="Model computation timed out")
    except Exception as e:
        logger.error("Subscription model error: %s", e)
        raise HTTPException(status_code=500, detail="Model execution failed")

    dataframe = df.to_dict(orient="records")
    retention = retention_matrix.tolist()

    return sanitize({
        "dataframe": dataframe,
        "milestones": milestones,
        "retention_matrix": retention,
    })


@router.post("/ecommerce")
def run_ecommerce(req: EcommerceRunRequest):
    validated = validate_config_dict(req.config)
    try:
        config = EcomConfig.from_dict(validated)
    except Exception as e:
        logger.warning("Invalid ecommerce config: %s", e)
        raise HTTPException(status_code=422, detail="Invalid configuration")

    sens = req.sensitivity if req.sensitivity is not None else build_ecom_scenario_params(config)["base"]

    try:
        logger.info("Running ecommerce model: %d months", config.total_months)
        df, milestones = run_with_timeout(run_ecom_model, config, sens)
    except TimeoutError:
        logger.error("Ecommerce model timed out (%d months)", config.total_months)
        raise HTTPException(status_code=504, detail="Model computation timed out")
    except Exception as e:
        logger.error("Ecommerce model error: %s", e)
        raise HTTPException(status_code=500, detail="Model execution failed")

    dataframe = df.to_dict(orient="records")

    return sanitize({
        "dataframe": dataframe,
        "milestones": milestones,
    })


@router.post("/saas")
def run_saas(req: SaasRunRequest):
    validated = validate_config_dict(req.config)
    try:
        config = SaasConfig.from_dict(validated)
    except Exception as e:
        logger.warning("Invalid saas config: %s", e)
        raise HTTPException(status_code=422, detail="Invalid configuration")

    sens = req.sensitivity if req.sensitivity is not None else build_saas_scenario_params(config)["base"]

    try:
        logger.info("Running SaaS model: %d months", config.total_months)
        df, milestones = run_with_timeout(run_saas_model, config, sens)
    except TimeoutError:
        logger.error("SaaS model timed out (%d months)", config.total_months)
        raise HTTPException(status_code=504, detail="Model computation timed out")
    except Exception as e:
        logger.error("SaaS model error: %s", e)
        raise HTTPException(status_code=500, detail="Model execution failed")

    dataframe = df.to_dict(orient="records")

    return sanitize({
        "dataframe": dataframe,
        "milestones": milestones,
    })
