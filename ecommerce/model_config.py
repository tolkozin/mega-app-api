"""EcomConfig dataclass — all e-commerce model parameters in a serializable structure."""

from dataclasses import dataclass, field, asdict
import json


@dataclass
class EcomPhaseConfig:
    avg_order_value: float = 50.0         # AOV ($)
    repeat_purchase_rate: float = 20.0    # % повторных покупок
    orders_per_returning: float = 1.5     # заказов/мес у returning customer
    cogs_pct: float = 40.0               # себестоимость % от выручки
    return_rate: float = 5.0             # % возвратов
    ad_budget: float = 5000.0            # рекламный бюджет/мес
    cpc: float = 1.50                    # cost per click
    click_to_purchase: float = 3.0       # конверсия клик → покупка %
    organic_pct: float = 20.0            # % органики от общего трафика
    discount_rate: float = 5.0           # средняя скидка %


@dataclass
class EcomConfig:
    product_type: str = "ecommerce"

    # General
    total_months: int = 36
    phase1_dur: int = 3
    phase2_dur: int = 6

    # Per-phase configs
    phase1: EcomPhaseConfig = field(default_factory=lambda: EcomPhaseConfig(
        avg_order_value=45.0, repeat_purchase_rate=10.0, orders_per_returning=1.2,
        cogs_pct=45.0, return_rate=5.0, ad_budget=3000.0, cpc=2.00,
        click_to_purchase=2.0, organic_pct=10.0, discount_rate=10.0,
    ))
    phase2: EcomPhaseConfig = field(default_factory=lambda: EcomPhaseConfig(
        avg_order_value=50.0, repeat_purchase_rate=20.0, orders_per_returning=1.5,
        cogs_pct=40.0, return_rate=5.0, ad_budget=8000.0, cpc=1.50,
        click_to_purchase=3.0, organic_pct=20.0, discount_rate=5.0,
    ))
    phase3: EcomPhaseConfig = field(default_factory=lambda: EcomPhaseConfig(
        avg_order_value=55.0, repeat_purchase_rate=30.0, orders_per_returning=2.0,
        cogs_pct=35.0, return_rate=4.0, ad_budget=20000.0, cpc=1.20,
        click_to_purchase=4.0, organic_pct=30.0, discount_rate=3.0,
    ))

    # OpEx
    salaries_base: float = 5000.0         # начальные зарплаты/мес
    salaries_growth: float = 3.0          # рост зарплат %/мес
    misc_costs: float = 2000.0            # прочие расходы/мес

    # Tax
    corporate_tax: float = 1.0            # %

    # Sensitivity
    sens_conv: float = 0.0
    sens_cpc: float = 0.0
    sens_aov: float = 0.0
    sens_organic: float = 0.0
    scenario_bound: float = 20.0

    # Monte Carlo
    mc_enabled: bool = False
    mc_iterations: int = 200
    mc_variance: float = 20.0

    @property
    def phase3_dur(self) -> int:
        return self.total_months - self.phase1_dur - self.phase2_dur

    def get_phase_config(self, phase: int) -> EcomPhaseConfig:
        return {1: self.phase1, 2: self.phase2, 3: self.phase3}[phase]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EcomConfig":
        d = d.copy()
        for key in ("phase1", "phase2", "phase3"):
            if key in d and isinstance(d[key], dict):
                d[key] = EcomPhaseConfig(**d[key])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "EcomConfig":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_defaults(cls) -> "EcomConfig":
        return cls()
