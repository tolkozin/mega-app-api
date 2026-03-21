"""CSV export endpoint."""

import io
import gzip
import logging

from fastapi import APIRouter, HTTPException, Request
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

from routers.models import validate_config_dict, run_with_timeout, TimeoutError

logger = logging.getLogger("revenuemap.export")

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    model_type: str
    config: dict
    sensitivity: dict | None = None


@router.post("/csv")
def export_csv(req: ExportRequest, request: Request):
    if req.model_type not in ("subscription", "ecommerce", "saas"):
        raise HTTPException(status_code=400, detail=f"Unknown model_type: {req.model_type}")

    validated = validate_config_dict(req.config)

    if req.model_type == "subscription":
        try:
            config = ModelConfig.from_dict(validated)
        except Exception as e:
            logger.warning("Invalid export config: %s", e)
            raise HTTPException(status_code=422, detail="Invalid configuration")

        sens = req.sensitivity if req.sensitivity is not None else build_scenario_params(config)["base"]

        try:
            logger.info("Exporting subscription model: %d months", config.total_months)
            df, _, _ = run_with_timeout(run_model, config, sens)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Model computation timed out")
        except Exception as e:
            logger.error("Export subscription error: %s", e)
            raise HTTPException(status_code=500, detail="Model execution failed")

    elif req.model_type == "ecommerce":
        try:
            config = EcomConfig.from_dict(validated)
        except Exception as e:
            logger.warning("Invalid export config: %s", e)
            raise HTTPException(status_code=422, detail="Invalid configuration")

        sens = req.sensitivity if req.sensitivity is not None else build_ecom_scenario_params(config)["base"]

        try:
            logger.info("Exporting ecommerce model: %d months", config.total_months)
            df, _ = run_with_timeout(run_ecom_model, config, sens)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Model computation timed out")
        except Exception as e:
            logger.error("Export ecommerce error: %s", e)
            raise HTTPException(status_code=500, detail="Model execution failed")

    else:  # saas
        try:
            config = SaasConfig.from_dict(validated)
        except Exception as e:
            logger.warning("Invalid export config: %s", e)
            raise HTTPException(status_code=422, detail="Invalid configuration")

        sens = req.sensitivity if req.sensitivity is not None else build_saas_scenario_params(config)["base"]

        try:
            logger.info("Exporting SaaS model: %d months", config.total_months)
            df, _ = run_with_timeout(run_saas_model, config, sens)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Model computation timed out")
        except Exception as e:
            logger.error("Export SaaS error: %s", e)
            raise HTTPException(status_code=500, detail="Model execution failed")

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue().encode("utf-8")

    # Gzip compress for large responses
    accept_encoding = request.headers.get("accept-encoding", "")
    if "gzip" in accept_encoding and len(csv_bytes) > 10_000:
        compressed = gzip.compress(csv_bytes)
        filename = f"{req.model_type}_model_export.csv"
        return StreamingResponse(
            iter([compressed]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Encoding": "gzip",
                "Content-Length": str(len(compressed)),
            },
        )

    filename = f"{req.model_type}_model_export.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(csv_bytes)),
        },
    )
