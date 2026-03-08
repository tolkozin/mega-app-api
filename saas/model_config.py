"""SaasConfig dataclass — all B2B SaaS model parameters in a serializable structure."""

from dataclasses import dataclass, field, asdict
import json


@dataclass
class SaasPhaseConfig:
    seats_per_account: float = 5.0        # avg seats per new account
    price_per_seat: float = 49.0          # $/seat/month
    annual_contract_pct: float = 70.0     # % of deals on annual contracts
    annual_discount: float = 15.0         # % discount for annual vs monthly

    ad_budget: float = 5000.0             # marketing spend/month
    cpl: float = 150.0                    # cost per lead
    lead_to_demo: float = 30.0            # % of leads that book a demo
    demo_to_close: float = 25.0           # % of demos that close

    sales_cycle_months: int = 1           # months from demo to close
    expansion_rate: float = 3.0           # % monthly seat expansion per account
    contraction_rate: float = 1.0         # % monthly seat contraction per account
    logo_churn_rate: float = 2.0          # % monthly customer churn

    cogs_per_seat: float = 5.0            # $/seat/month (hosting, support)
    organic_leads_pct: float = 20.0       # % of leads from organic/inbound


@dataclass
class SaasConfig:
    product_type: str = "saas"

    # General
    total_months: int = 36
    phase1_dur: int = 3
    phase2_dur: int = 9

    # Per-phase configs
    phase1: SaasPhaseConfig = field(default_factory=lambda: SaasPhaseConfig(
        seats_per_account=3, price_per_seat=39, annual_contract_pct=50, annual_discount=15,
        ad_budget=3000, cpl=200, lead_to_demo=20, demo_to_close=15,
        sales_cycle_months=2, expansion_rate=1, contraction_rate=0.5, logo_churn_rate=3,
        cogs_per_seat=6, organic_leads_pct=10,
    ))
    phase2: SaasPhaseConfig = field(default_factory=lambda: SaasPhaseConfig(
        seats_per_account=5, price_per_seat=49, annual_contract_pct=70, annual_discount=15,
        ad_budget=8000, cpl=150, lead_to_demo=30, demo_to_close=25,
        sales_cycle_months=1, expansion_rate=3, contraction_rate=1, logo_churn_rate=2,
        cogs_per_seat=5, organic_leads_pct=20,
    ))
    phase3: SaasPhaseConfig = field(default_factory=lambda: SaasPhaseConfig(
        seats_per_account=8, price_per_seat=49, annual_contract_pct=80, annual_discount=15,
        ad_budget=20000, cpl=120, lead_to_demo=35, demo_to_close=30,
        sales_cycle_months=1, expansion_rate=5, contraction_rate=1, logo_churn_rate=1.5,
        cogs_per_seat=4, organic_leads_pct=30,
    ))

    # OpEx
    salaries_base: float = 8000.0
    salaries_growth: float = 3.0
    misc_costs: float = 3000.0

    # Tax
    corporate_tax: float = 1.0

    # Initial state
    initial_customers: int = 0
    initial_seats: int = 0
    investment: float = 100000.0

    # Sensitivity
    sens_conv: float = 0.0
    sens_churn: float = 0.0
    sens_expansion: float = 0.0
    sens_organic: float = 0.0
    scenario_bound: float = 20.0

    # Monte Carlo
    mc_enabled: bool = False
    mc_iterations: int = 200
    mc_variance: float = 20.0

    @property
    def phase3_dur(self) -> int:
        return self.total_months - self.phase1_dur - self.phase2_dur

    def get_phase_config(self, phase: int) -> SaasPhaseConfig:
        return {1: self.phase1, 2: self.phase2, 3: self.phase3}[phase]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SaasConfig":
        d = d.copy()
        for key in ("phase1", "phase2", "phase3"):
            if key in d and isinstance(d[key], dict):
                d[key] = SaasPhaseConfig(**d[key])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "SaasConfig":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_defaults(cls) -> "SaasConfig":
        return cls()
