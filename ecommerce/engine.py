"""Pure data engine — run_ecom_model(config, sens_params) with no Streamlit dependencies."""

import numpy as np
import pandas as pd

from ecommerce.model_config import EcomConfig


def run_ecom_model(config: EcomConfig, sens_params: dict | None = None):
    """Run the e-commerce financial model. Returns (df, milestones).

    Args:
        config: EcomConfig with all parameters.
        sens_params: dict with keys conv, cpc, aov, organic (fractional, e.g. 0.2 = +20%).
    """
    if sens_params is None:
        sens_params = {"conv": 0, "cpc": 0, "aov": 0, "organic": 0}

    N = config.total_months
    months = np.arange(1, N + 1)
    df = pd.DataFrame({"Month": months})

    conv_factor = 1 + sens_params.get("conv", 0)
    cpc_factor = 1 + sens_params.get("cpc", 0)
    aov_factor = 1 + sens_params.get("aov", 0)
    organic_factor = 1 + sens_params.get("organic", 0)

    p1_end = config.phase1_dur
    p2_end = config.phase1_dur + config.phase2_dur

    def get_phase(m):
        if m <= p1_end:
            return 1
        elif m <= p2_end:
            return 2
        return 3

    df["Product Phase"] = df["Month"].apply(get_phase)

    p1 = config.phase1
    p2 = config.phase2
    p3 = config.phase3

    phase_cfg = {
        1: p1,
        2: p2,
        3: p3,
    }

    # ===================== TRAFFIC =====================
    # Paid: Ad Budget / CPC = Clicks, Clicks * click_to_purchase% = Paid Purchases
    # Organic: organic_pct% of total traffic comes from organic sources

    paid_clicks = np.zeros(N)
    paid_purchases = np.zeros(N)
    organic_purchases = np.zeros(N)
    total_purchases = np.zeros(N)
    ad_budgets = np.zeros(N)
    cpc_arr = np.zeros(N)
    aov_arr = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        ad_budgets[i] = cfg.ad_budget
        cpc_arr[i] = cfg.cpc * cpc_factor
        aov_arr[i] = cfg.avg_order_value * aov_factor

        if cpc_arr[i] > 0:
            paid_clicks[i] = ad_budgets[i] / cpc_arr[i]
        conv_rate = cfg.click_to_purchase / 100.0 * conv_factor
        paid_purchases[i] = paid_clicks[i] * conv_rate

        # Organic: organic_pct means organic is X% of total traffic
        # So paid is (100 - organic_pct)% → total = paid / (1 - organic_pct/100)
        organic_pct = min(99.0, cfg.organic_pct * organic_factor)
        if organic_pct > 0 and organic_pct < 100:
            total_from_paid = paid_purchases[i] / max(0.01, (1 - organic_pct / 100.0))
            organic_purchases[i] = total_from_paid - paid_purchases[i]
        total_purchases[i] = paid_purchases[i] + organic_purchases[i]

    df["Ad Budget"] = ad_budgets
    df["CPC"] = cpc_arr
    df["Paid Clicks"] = paid_clicks
    df["Paid Purchases"] = paid_purchases
    df["Organic Purchases"] = organic_purchases
    df["Total New Purchases"] = total_purchases

    # ===================== CUSTOMER COHORTS =====================
    # Track cumulative unique customers and returning customers
    cumulative_customers = np.zeros(N)
    new_customers = np.zeros(N)
    returning_orders = np.zeros(N)
    total_orders = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        # New customers this month = new purchases (first-time buyers)
        new_customers[i] = total_purchases[i]

        # Cumulative customer base
        if i == 0:
            cumulative_customers[i] = new_customers[i]
        else:
            cumulative_customers[i] = cumulative_customers[i - 1] + new_customers[i]

        # Returning customers: previous customer base × repeat_purchase_rate × orders_per_returning
        if i > 0:
            repeat_rate = cfg.repeat_purchase_rate / 100.0
            returning_orders[i] = cumulative_customers[i - 1] * repeat_rate * cfg.orders_per_returning

        total_orders[i] = new_customers[i] + returning_orders[i]

    df["New Customers"] = new_customers
    df["Cumulative Customers"] = cumulative_customers
    df["Returning Orders"] = returning_orders
    df["Total Orders"] = total_orders

    # ===================== REVENUE =====================
    gross_revenue = np.zeros(N)
    returns_amount = np.zeros(N)
    discounts_amount = np.zeros(N)
    net_revenue = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        gross_revenue[i] = total_orders[i] * aov_arr[i]
        returns_amount[i] = gross_revenue[i] * (cfg.return_rate / 100.0)
        discounts_amount[i] = gross_revenue[i] * (cfg.discount_rate / 100.0)
        net_revenue[i] = gross_revenue[i] - returns_amount[i] - discounts_amount[i]

    df["Gross Revenue"] = gross_revenue
    df["Returns"] = returns_amount
    df["Discounts"] = discounts_amount
    df["Net Revenue"] = net_revenue

    # ===================== UNIT ECONOMICS =====================
    cogs = np.zeros(N)
    gross_profit = np.zeros(N)
    gross_margin_pct = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        cogs[i] = net_revenue[i] * (cfg.cogs_pct / 100.0)
        gross_profit[i] = net_revenue[i] - cogs[i]
        if net_revenue[i] > 0:
            gross_margin_pct[i] = gross_profit[i] / net_revenue[i] * 100
        else:
            gross_margin_pct[i] = 0

    df["COGS"] = cogs
    df["Gross Profit"] = gross_profit
    df["Gross Margin %"] = gross_margin_pct

    # CAC = Ad Budget / New Customers (paid only)
    df["CAC"] = np.where(paid_purchases > 0, ad_budgets / paid_purchases, np.nan)

    # ===================== OPEX =====================
    salaries = np.zeros(N)
    for i in range(N):
        salaries[i] = config.salaries_base * ((1 + config.salaries_growth / 100.0) ** i)

    df["Marketing"] = ad_budgets
    df["Salaries"] = salaries
    df["Misc Costs"] = config.misc_costs
    df["Total Expenses"] = df["COGS"] + df["Marketing"] + df["Salaries"] + df["Misc Costs"]

    # ===================== P&L =====================
    df["EBITDA"] = df["Net Revenue"] - df["COGS"] - df["Marketing"] - df["Salaries"] - df["Misc Costs"]
    df["Corporate Tax"] = df["EBITDA"].apply(lambda x: x * (config.corporate_tax / 100.0) if x > 0 else 0)
    df["Net Profit"] = df["EBITDA"] - df["Corporate Tax"]
    df["Net Cash Flow"] = df["Net Profit"]

    # Cash Balance (no separate investment — expenses already captured)
    cash_bal = np.cumsum(df["Net Cash Flow"].values)
    df["Cash Balance"] = cash_bal

    df["Cumulative Net Profit"] = df["Net Profit"].cumsum()
    df["Cumulative Revenue"] = df["Net Revenue"].cumsum()
    df["Cumulative Marketing"] = df["Marketing"].cumsum()

    # ===================== METRICS =====================

    # LTV approximation: avg revenue per customer over lifetime
    # Simple: (ARPU * Gross Margin% * avg_lifetime)
    # avg_lifetime ≈ 1 / (1 - repeat_rate) months (geometric series)
    ltv = np.zeros(N)
    ltv_cac = np.zeros(N)
    roas = np.zeros(N)
    cac_payback = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        repeat_rate = cfg.repeat_purchase_rate / 100.0
        if total_orders[i] > 0:
            revenue_per_order = net_revenue[i] / total_orders[i]
        else:
            revenue_per_order = 0

        gm = cfg.cogs_pct / 100.0
        margin_per_order = revenue_per_order * (1 - gm)

        # Expected orders per customer over lifetime
        if repeat_rate < 1.0:
            lifetime_orders = 1.0 / (1.0 - repeat_rate)
        else:
            lifetime_orders = 12.0  # cap

        ltv[i] = margin_per_order * lifetime_orders

        cac_val = df.loc[i, "CAC"]
        if not np.isnan(cac_val) and cac_val > 0:
            ltv_cac[i] = ltv[i] / cac_val
            if margin_per_order > 0:
                cac_payback[i] = cac_val / margin_per_order
            else:
                cac_payback[i] = np.nan
        else:
            ltv_cac[i] = np.nan
            cac_payback[i] = np.nan

        if ad_budgets[i] > 0:
            roas[i] = net_revenue[i] / ad_budgets[i]
        else:
            roas[i] = np.nan

    df["LTV"] = ltv
    df["LTV/CAC"] = ltv_cac
    df["ROAS"] = roas
    df["CAC Payback"] = cac_payback

    # AOV trend (actual realized)
    df["AOV"] = np.where(total_orders > 0, gross_revenue / total_orders, 0)
    # Repeat Rate trend (actual)
    df["Repeat Rate %"] = np.where(
        cumulative_customers > 0,
        np.where(np.arange(N) > 0, returning_orders / np.maximum(np.roll(cumulative_customers, 1), 1) * 100, 0),
        0
    )

    # Burn Rate & Runway
    df["Burn Rate"] = df["Net Cash Flow"].apply(lambda x: abs(x) if x < 0 else 0)
    runway = np.full(N, np.nan)
    for j in range(N):
        if df.loc[j, "Net Cash Flow"] < 0 and cash_bal[j] > 0:
            runway[j] = cash_bal[j] / abs(df.loc[j, "Net Cash Flow"])
    df["Runway (Months)"] = runway

    # ROI (cumulative)
    total_costs_cum = (df["Total Expenses"] + df["Corporate Tax"]).cumsum()
    total_investment = df["Marketing"].sum()  # Total marketing as "investment"
    df["ROI %"] = np.where(
        df["Cumulative Marketing"] > 0,
        ((df["Cumulative Revenue"] - total_costs_cum) / df["Cumulative Marketing"]) * 100,
        0
    )

    # Cumulative ROAS
    df["Cumulative ROAS"] = df["Cumulative Revenue"] / df["Cumulative Marketing"].replace(0, np.nan)

    # ===================== MILESTONES =====================
    milestones = {}

    be_months = df[df["Net Profit"] > 0]["Month"]
    milestones["break_even_month"] = int(be_months.iloc[0]) if len(be_months) > 0 else None

    cum_be = df[df["Cumulative Net Profit"] > 0]["Month"]
    milestones["cumulative_break_even"] = int(cum_be.iloc[0]) if len(cum_be) > 0 else None

    cf_pos = df[df["Net Cash Flow"] > 0]["Month"]
    milestones["cf_positive_month"] = int(cf_pos.iloc[0]) if len(cf_pos) > 0 else None

    cash_neg = df[df["Cash Balance"] < 0]["Month"]
    milestones["runway_out_month"] = int(cash_neg.iloc[0]) if len(cash_neg) > 0 else None

    for threshold in [1000, 10000, 100000]:
        om = df[df["Total Orders"] >= threshold]["Month"]
        milestones[f"orders_{threshold}"] = int(om.iloc[0]) if len(om) > 0 else None

    for threshold in [10000, 50000, 100000, 1000000]:
        rm = df[df["Net Revenue"] >= threshold]["Month"]
        milestones[f"revenue_{threshold}"] = int(rm.iloc[0]) if len(rm) > 0 else None

    for threshold in [1000, 10000, 100000]:
        cm = df[df["Cumulative Customers"] >= threshold]["Month"]
        milestones[f"customers_{threshold}"] = int(cm.iloc[0]) if len(cm) > 0 else None

    return df, milestones
