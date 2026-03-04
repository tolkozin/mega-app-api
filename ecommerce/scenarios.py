"""Scenario sensitivity parameter builders for e-commerce."""

from ecommerce.model_config import EcomConfig


def build_ecom_scenario_params(config: EcomConfig) -> dict:
    """Build base/pessimistic/optimistic sensitivity dicts from config.

    Returns:
        {"base": {...}, "pessimistic": {...}, "optimistic": {...}}
    """
    base_sens = {
        "conv": config.sens_conv / 100.0,
        "cpc": config.sens_cpc / 100.0,
        "aov": config.sens_aov / 100.0,
        "organic": config.sens_organic / 100.0,
    }
    bound = config.scenario_bound / 100.0

    pessimistic_sens = {
        "conv": base_sens["conv"] - bound,
        "cpc": base_sens["cpc"] + bound,      # higher CPC = worse
        "aov": base_sens["aov"] - bound,
        "organic": base_sens["organic"] - bound,
    }

    optimistic_sens = {
        "conv": base_sens["conv"] + bound,
        "cpc": base_sens["cpc"] - bound,       # lower CPC = better
        "aov": base_sens["aov"] + bound,
        "organic": base_sens["organic"] + bound,
    }

    return {
        "base": base_sens,
        "pessimistic": pessimistic_sens,
        "optimistic": optimistic_sens,
    }
