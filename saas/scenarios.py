"""Scenario sensitivity parameter builders for B2B SaaS."""

from saas.model_config import SaasConfig


def build_saas_scenario_params(config: SaasConfig) -> dict:
    """Build base/pessimistic/optimistic sensitivity dicts from config.

    Returns:
        {"base": {...}, "pessimistic": {...}, "optimistic": {...}}
    """
    base_sens = {
        "conv": config.sens_conv / 100.0,
        "churn": config.sens_churn / 100.0,
        "expansion": config.sens_expansion / 100.0,
        "organic": config.sens_organic / 100.0,
    }
    bound = config.scenario_bound / 100.0

    pessimistic_sens = {
        "conv": base_sens["conv"] - bound,
        "churn": base_sens["churn"] + bound,        # higher churn = worse
        "expansion": base_sens["expansion"] - bound,  # less expansion = worse
        "organic": base_sens["organic"] - bound,
    }

    optimistic_sens = {
        "conv": base_sens["conv"] + bound,
        "churn": base_sens["churn"] - bound,          # lower churn = better
        "expansion": base_sens["expansion"] + bound,    # more expansion = better
        "organic": base_sens["organic"] + bound,
    }

    return {
        "base": base_sens,
        "pessimistic": pessimistic_sens,
        "optimistic": optimistic_sens,
    }
