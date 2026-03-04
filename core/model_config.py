"""ModelConfig dataclass — all 67+ model parameters in a serializable structure."""

from dataclasses import dataclass, field, asdict
import json


@dataclass
class PhaseConfig:
    investment: float = 0.0
    salaries_total: float = 0.0
    misc_total: float = 0.0
    ad_budget: float = 0.0
    cpi: float = 7.50
    conv_trial: float = 0.0       # percentage, e.g. 20.0
    conv_paid: float = 0.0        # percentage, e.g. 20.0
    churn_mult: float = 1.0

    # Ad growth
    ad_growth_mode: str = "Percentage (%)"
    ad_growth_pct: float = 0.0
    ad_growth_abs: float = 0.0
    cpi_degradation: float = 0.0

    # Organic
    organic_growth_mode: str = "Percentage (%)"
    organic_growth_pct: float = 0.0
    organic_growth_abs: float = 0.0
    organic_conv_trial: float = 0.0   # percentage
    organic_conv_paid: float = 0.0    # percentage
    organic_spend: float = 0.0

    # Pricing
    price_weekly: float = 4.99
    price_monthly: float = 7.99
    price_annual: float = 49.99

    # Mix (fractions, 0-1)
    mix_weekly: float = 0.0
    mix_monthly: float = 0.48
    mix_annual: float = 0.52

    # COGS
    cogs: float = 0.10


@dataclass
class ModelConfig:
    # General
    total_months: int = 60
    phase1_dur: int = 3
    phase2_dur: int = 3

    # Sensitivity
    sens_conv: float = 0.0
    sens_churn: float = 0.0
    sens_cpi: float = 0.0
    sens_organic: float = 0.0
    scenario_bound: float = 20.0

    # Monte Carlo
    mc_enabled: bool = False
    mc_iterations: int = 200
    mc_variance: float = 20.0

    # Taxes & Fees
    corporate_tax: float = 1.0
    store_split: float = 50.0
    app_store_comm: float = 15.0
    web_comm_pct: float = 3.5
    web_comm_fixed: float = 0.50
    bank_fee: float = 1.0

    # Retention & Churn
    weekly_cancel_rate: float = 15.0
    monthly_churn_rate: float = 10.0
    annual_non_renewal: float = 30.0

    # Trial & Refunds
    trial_days: int = 7
    refund_rate: float = 2.0

    # Expansion
    upgrade_rate: float = 2.0
    downgrade_rate: float = 5.0

    # Organic starting traffic
    starting_organic: float = 0.0

    # Per-phase configs
    phase1: PhaseConfig = field(default_factory=lambda: PhaseConfig(
        investment=100000.0, salaries_total=17475.0, misc_total=8419.0,
        ad_budget=0.0, cpi=7.50, conv_trial=0.0, conv_paid=0.0,
        churn_mult=1.0,
        ad_growth_mode="Percentage (%)", ad_growth_pct=0.0, ad_growth_abs=0.0,
        cpi_degradation=0.0,
        organic_growth_mode="Percentage (%)", organic_growth_pct=0.0, organic_growth_abs=0.0,
        organic_conv_trial=0.0, organic_conv_paid=0.0, organic_spend=0.0,
        price_weekly=4.99, price_monthly=7.99, price_annual=49.99,
        mix_weekly=0.0, mix_monthly=0.48, mix_annual=0.52,
        cogs=0.10,
    ))
    phase2: PhaseConfig = field(default_factory=lambda: PhaseConfig(
        investment=0.0, salaries_total=3600.0, misc_total=750.0,
        ad_budget=5000.0, cpi=7.50, conv_trial=20.0, conv_paid=20.0,
        churn_mult=1.5,
        ad_growth_mode="Percentage (%)", ad_growth_pct=5.0, ad_growth_abs=5000.0,
        cpi_degradation=1.0,
        organic_growth_mode="Percentage (%)", organic_growth_pct=10.0, organic_growth_abs=50.0,
        organic_conv_trial=25.0, organic_conv_paid=25.0, organic_spend=500.0,
        price_weekly=4.99, price_monthly=7.99, price_annual=49.99,
        mix_weekly=0.0, mix_monthly=0.48, mix_annual=0.52,
        cogs=0.10,
    ))
    phase3: PhaseConfig = field(default_factory=lambda: PhaseConfig(
        investment=0.0, salaries_total=64800.0, misc_total=13500.0,
        ad_budget=150000.0, cpi=7.50, conv_trial=25.0, conv_paid=25.0,
        churn_mult=1.0,
        ad_growth_mode="Percentage (%)", ad_growth_pct=5.0, ad_growth_abs=5000.0,
        cpi_degradation=1.0,
        organic_growth_mode="Percentage (%)", organic_growth_pct=15.0, organic_growth_abs=500.0,
        organic_conv_trial=35.0, organic_conv_paid=35.0, organic_spend=2000.0,
        price_weekly=4.99, price_monthly=7.99, price_annual=49.99,
        mix_weekly=0.0, mix_monthly=0.48, mix_annual=0.52,
        cogs=0.10,
    ))

    @property
    def phase3_dur(self) -> int:
        return self.total_months - self.phase1_dur - self.phase2_dur

    def get_phase_config(self, phase: int) -> PhaseConfig:
        return {1: self.phase1, 2: self.phase2, 3: self.phase3}[phase]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        d = d.copy()
        for key in ("phase1", "phase2", "phase3"):
            if key in d and isinstance(d[key], dict):
                d[key] = PhaseConfig(**d[key])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "ModelConfig":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_defaults(cls) -> "ModelConfig":
        return cls()
