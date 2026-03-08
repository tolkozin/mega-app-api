"""CSV export endpoint."""

import io
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.model_config import ModelConfig
from core.engine import run_model
from core.scenarios import build_scenario_params

from ecommerce.model_config import EcomConfig
from ecommerce.engine import run_ecom_model
from ecommerce.scenarios import build_ecom_scenario_params

from saas.model_config import SaasConfig
from saas.engine import run_saas_model
from saas.scenarios import build_saas_scenario_params

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    model_type: str  # "subscription" or "ecommerce"
    config: dict
    sensitivity: dict | None = None


@router.post("/csv")
def export_csv(req: ExportRequest):
    if req.model_type == "subscription":
        try:
            config = ModelConfig.from_dict(req.config)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

        if req.sensitivity is not None:
            sens = req.sensitivity
        else:
            scenarios = build_scenario_params(config)
            sens = scenarios["base"]

        try:
            df, _milestones, _retention = run_model(config, sens)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Model execution error: {e}")

    elif req.model_type == "ecommerce":
        try:
            config = EcomConfig.from_dict(req.config)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

        if req.sensitivity is not None:
            sens = req.sensitivity
        else:
            scenarios = build_ecom_scenario_params(config)
            sens = scenarios["base"]

        try:
            df, _milestones = run_ecom_model(config, sens)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Model execution error: {e}")

    elif req.model_type == "saas":
        try:
            config = SaasConfig.from_dict(req.config)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

        if req.sensitivity is not None:
            sens = req.sensitivity
        else:
            scenarios = build_saas_scenario_params(config)
            sens = scenarios["base"]

        try:
            df, _milestones = run_saas_model(config, sens)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Model execution error: {e}")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown model_type: {req.model_type}")

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    filename = f"{req.model_type}_model_export.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
