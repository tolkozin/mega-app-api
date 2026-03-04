"""Model execution endpoints — subscription and e-commerce."""

import math
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.model_config import ModelConfig
from core.engine import run_model
from core.scenarios import build_scenario_params

from ecommerce.model_config import EcomConfig
from ecommerce.engine import run_ecom_model
from ecommerce.scenarios import build_ecom_scenario_params

router = APIRouter(prefix="/api/run", tags=["models"])


# --------------- helpers ---------------

def sanitize(obj: Any) -> Any:
    """Replace NaN/Infinity floats with None for JSON serialization."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(i) for i in obj]
    return obj


# --------------- request schemas ---------------

class SubscriptionRunRequest(BaseModel):
    config: dict
    sensitivity: dict | None = None


class EcommerceRunRequest(BaseModel):
    config: dict
    sensitivity: dict | None = None


# --------------- endpoints ---------------

@router.post("/subscription")
def run_subscription(req: SubscriptionRunRequest):
    try:
        config = ModelConfig.from_dict(req.config)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    # Determine sensitivity params
    if req.sensitivity is not None:
        sens = req.sensitivity
    else:
        scenarios = build_scenario_params(config)
        sens = scenarios["base"]

    try:
        df, milestones, retention_matrix = run_model(config, sens)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model execution error: {e}")

    dataframe = df.to_dict(orient="records")
    retention = retention_matrix.tolist()

    return sanitize({
        "dataframe": dataframe,
        "milestones": milestones,
        "retention_matrix": retention,
    })


@router.post("/ecommerce")
def run_ecommerce(req: EcommerceRunRequest):
    try:
        config = EcomConfig.from_dict(req.config)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    # Determine sensitivity params
    if req.sensitivity is not None:
        sens = req.sensitivity
    else:
        scenarios = build_ecom_scenario_params(config)
        sens = scenarios["base"]

    try:
        df, milestones = run_ecom_model(config, sens)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model execution error: {e}")

    dataframe = df.to_dict(orient="records")

    return sanitize({
        "dataframe": dataframe,
        "milestones": milestones,
    })
