"""Scenario sensitivity parameter builders."""

from core.model_config import ModelConfig


def build_scenario_params(config: ModelConfig) -> dict:
    """Build base/pessimistic/optimistic sensitivity dicts from config.

    Returns:
        {"base": {...}, "pessimistic": {...}, "optimistic": {...}}
    """
    base_sens = {
        "conv": config.sens_conv / 100.0,
        "churn": config.sens_churn / 100.0,
        "cpi": config.sens_cpi / 100.0,
        "organic": config.sens_organic / 100.0,
    }
    bound = config.scenario_bound / 100.0

    pessimistic_sens = {
        "conv": base_sens["conv"] - bound,
        "churn": base_sens["churn"] + bound,
        "cpi": base_sens["cpi"] + bound,
        "organic": base_sens["organic"] - bound,
    }

    optimistic_sens = {
        "conv": base_sens["conv"] + bound,
        "churn": base_sens["churn"] - bound,
        "cpi": base_sens["cpi"] - bound,
        "organic": base_sens["organic"] + bound,
    }

    return {
        "base": base_sens,
        "pessimistic": pessimistic_sens,
        "optimistic": optimistic_sens,
    }
