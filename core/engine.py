"""Pure data engine — run_model(config, sens_params) with no Streamlit dependencies."""

import numpy as np
import pandas as pd

from core.model_config import ModelConfig


def run_model(config: ModelConfig, sens_params: dict | None = None):
    """Run the financial model. Returns (df, milestones, retention_matrix).

    Args:
        config: ModelConfig with all parameters.
        sens_params: dict with keys conv, churn, cpi, organic (fractional, e.g. 0.2 = +20%).
    """
    if sens_params is None:
        sens_params = {"conv": 0, "churn": 0, "cpi": 0, "organic": 0}

    N = config.total_months
    months = np.arange(1, N + 1)
    df = pd.DataFrame({"Month": months})

    conv_factor = 1 + sens_params.get("conv", 0)
    churn_factor = 1 + sens_params.get("churn", 0)
    cpi_factor = 1 + sens_params.get("cpi", 0)
    organic_factor = 1 + sens_params.get("organic", 0)

    p1_end = config.phase1_dur
    p2_end = config.phase1_dur + config.phase2_dur
    phase3_dur = config.phase3_dur

    def get_phase(m):
        if m <= p1_end:
            return 1
        elif m <= p2_end:
            return 2
        return 3

    df["Product Phase"] = df["Month"].apply(get_phase)

    # Per-phase config dicts (intermediate representation for fast lookup)
    p1 = config.phase1
    p2 = config.phase2
    p3 = config.phase3

    phase_cfg = {
        1: {
            "ad": p1.ad_budget, "cpi": p1.cpi,
            "ct": p1.conv_trial / 100.0 * conv_factor,
            "cp": p1.conv_paid / 100.0 * conv_factor,
            "sal": p1.salaries_total / config.phase1_dur,
            "misc": p1.misc_total / config.phase1_dur,
            "inv": p1.investment, "churn_m": 1.0,
            "ad_growth_mode": "Percentage (%)", "ad_growth_pct": 0.0, "ad_growth_abs": 0.0,
            "cpi_deg": 0.0,
            "org_growth_mode": p1.organic_growth_mode,
            "org_growth_pct": p1.organic_growth_pct, "org_growth_abs": p1.organic_growth_abs,
            "org_conv_trial": p1.organic_conv_trial / 100.0 * conv_factor,
            "org_conv_paid": p1.organic_conv_paid / 100.0 * conv_factor,
            "org_spend": p1.organic_spend,
            "mix_w": p1.mix_weekly, "mix_m": p1.mix_monthly, "mix_a": p1.mix_annual,
            "pr_w": p1.price_weekly, "pr_m": p1.price_monthly, "pr_a": p1.price_annual,
            "cogs": p1.cogs,
        },
        2: {
            "ad": p2.ad_budget, "cpi": p2.cpi,
            "ct": p2.conv_trial / 100.0 * conv_factor,
            "cp": p2.conv_paid / 100.0 * conv_factor,
            "sal": p2.salaries_total / config.phase2_dur,
            "misc": p2.misc_total / config.phase2_dur,
            "inv": p2.investment, "churn_m": p2.churn_mult,
            "ad_growth_mode": p2.ad_growth_mode, "ad_growth_pct": p2.ad_growth_pct, "ad_growth_abs": p2.ad_growth_abs,
            "cpi_deg": p2.cpi_degradation,
            "org_growth_mode": p2.organic_growth_mode,
            "org_growth_pct": p2.organic_growth_pct, "org_growth_abs": p2.organic_growth_abs,
            "org_conv_trial": p2.organic_conv_trial / 100.0 * conv_factor,
            "org_conv_paid": p2.organic_conv_paid / 100.0 * conv_factor,
            "org_spend": p2.organic_spend,
            "mix_w": p2.mix_weekly, "mix_m": p2.mix_monthly, "mix_a": p2.mix_annual,
            "pr_w": p2.price_weekly, "pr_m": p2.price_monthly, "pr_a": p2.price_annual,
            "cogs": p2.cogs,
        },
        3: {
            "ad": p3.ad_budget, "cpi": p3.cpi,
            "ct": p3.conv_trial / 100.0 * conv_factor,
            "cp": p3.conv_paid / 100.0 * conv_factor,
            "sal": p3.salaries_total / phase3_dur,
            "misc": p3.misc_total / phase3_dur,
            "inv": p3.investment, "churn_m": p3.churn_mult,
            "ad_growth_mode": p3.ad_growth_mode, "ad_growth_pct": p3.ad_growth_pct, "ad_growth_abs": p3.ad_growth_abs,
            "cpi_deg": p3.cpi_degradation,
            "org_growth_mode": p3.organic_growth_mode,
            "org_growth_pct": p3.organic_growth_pct, "org_growth_abs": p3.organic_growth_abs,
            "org_conv_trial": p3.organic_conv_trial / 100.0 * conv_factor,
            "org_conv_paid": p3.organic_conv_paid / 100.0 * conv_factor,
            "org_spend": p3.organic_spend,
            "mix_w": p3.mix_weekly, "mix_m": p3.mix_monthly, "mix_a": p3.mix_annual,
            "pr_w": p3.price_weekly, "pr_m": p3.price_monthly, "pr_a": p3.price_annual,
            "cogs": p3.cogs,
        },
    }

    # --- Ad Budget with per-phase growth ---
    ad_budgets = np.zeros(N)
    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]
        base = cfg["ad"]
        if phase == 1:
            m_in = i
        elif phase == 2:
            m_in = i - p1_end
        else:
            m_in = i - p2_end
        if cfg["ad_growth_mode"] == "Percentage (%)":
            ad_budgets[i] = base * ((1 + cfg["ad_growth_pct"] / 100.0) ** m_in)
        else:
            ad_budgets[i] = base + cfg["ad_growth_abs"] * m_in
    df["Ad Budget"] = ad_budgets

    # --- CPI with per-phase degradation and sensitivity ---
    cpi_arr = np.zeros(N)
    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]
        base_cpi = cfg["cpi"] * cpi_factor
        base_ad = cfg["ad"]
        deg = cfg["cpi_deg"]
        extra = max(0, ad_budgets[i] - base_ad) / 1000.0
        cpi_arr[i] = base_cpi * (1 + (deg / 100.0) * extra)
    df["CPI"] = cpi_arr
    df["Installs"] = np.where(df["Ad Budget"] > 0, df["Ad Budget"] / df["CPI"], 0)

    # --- Per-phase conversions ---
    conv_t = np.array([phase_cfg[get_phase(m)]["ct"] for m in months])
    conv_p = np.array([phase_cfg[get_phase(m)]["cp"] for m in months])
    df["New Trials"] = df["Installs"].values * conv_t

    # Trial delay: only full months count (3-day trial = 0 delay, 30-day = 1 month)
    trial_delay = config.trial_days // 30
    paid_new = df["New Trials"].values * conv_p
    if trial_delay > 0:
        paid_new = np.concatenate([np.zeros(trial_delay), paid_new[:N - trial_delay]])
    df["Paid New Paid Users"] = paid_new

    # --- Organic (per phase, traffic carries over) ---
    org_traffic = np.zeros(N)
    current_organic = config.starting_organic
    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]
        if i == 0:
            org_traffic[i] = current_organic
        else:
            prev_phase = get_phase(i)
            if prev_phase != phase:
                current_organic = org_traffic[i - 1]
            if cfg["org_growth_mode"] == "Percentage (%)":
                org_traffic[i] = org_traffic[i - 1] * (1 + cfg["org_growth_pct"] / 100.0 * organic_factor)
            else:
                org_traffic[i] = org_traffic[i - 1] + cfg["org_growth_abs"] * organic_factor
        org_traffic[i] = max(0, org_traffic[i])
    df["Organic Traffic"] = org_traffic

    # Organic conversions per phase
    org_ct = np.array([phase_cfg[get_phase(m)]["org_conv_trial"] for m in months])
    org_cp = np.array([phase_cfg[get_phase(m)]["org_conv_paid"] for m in months])
    org_new = org_traffic * org_ct * org_cp
    if trial_delay > 0:
        org_new = np.concatenate([np.zeros(trial_delay), org_new[:N - trial_delay]])
    df["Organic New Paid Users"] = org_new
    df["New Paid Users"] = df["Paid New Paid Users"] + df["Organic New Paid Users"]
    df["New Web Users"] = df["New Paid Users"] * (100 - config.store_split) / 100.0
    df["New Store Users"] = df["New Paid Users"] * config.store_split / 100.0

    # --- Churn rates ---
    base_churn_w = 1 - (1 - config.weekly_cancel_rate / 100.0) ** 4.33
    base_churn_m = config.monthly_churn_rate / 100.0
    base_non_renewal = config.annual_non_renewal / 100.0
    churn_mult_map = {1: 1.0, 2: p2.churn_mult, 3: p3.churn_mult}

    # --- Per-phase mix and pricing ---
    def get_mix(phase):
        cfg = phase_cfg[phase]
        return cfg["mix_w"], cfg["mix_m"], cfg["mix_a"]

    def get_prices(phase):
        cfg = phase_cfg[phase]
        return cfg["pr_w"], cfg["pr_m"], cfg["pr_a"]

    # --- Cohort matrices ---
    cohorts = {}
    for plat in ["web", "store"]:
        for plan in ["weekly", "monthly", "annual"]:
            cohorts[f"{plat}_{plan}"] = np.zeros((N, N))

    for i in range(N):
        nw = df.loc[i, "New Web Users"]
        ns = df.loc[i, "New Store Users"]
        phase_i = get_phase(i + 1)
        mw, mm, ma = get_mix(phase_i)

        cohorts["web_weekly"][i, i] = nw * mw
        cohorts["web_monthly"][i, i] = nw * mm
        cohorts["web_annual"][i, i] = nw * ma
        cohorts["store_weekly"][i, i] = ns * mw
        cohorts["store_monthly"][i, i] = ns * mm
        cohorts["store_annual"][i, i] = ns * ma

        for j in range(i + 1, N):
            phase_j = get_phase(j + 1)
            mult = churn_mult_map[phase_j] * churn_factor

            cw = min(1.0, base_churn_w * mult)
            cohorts["web_weekly"][i, j] = cohorts["web_weekly"][i, j - 1] * (1 - cw)
            cohorts["store_weekly"][i, j] = cohorts["store_weekly"][i, j - 1] * (1 - cw)

            cm = min(1.0, base_churn_m * mult)
            cohorts["web_monthly"][i, j] = cohorts["web_monthly"][i, j - 1] * (1 - cm)
            cohorts["store_monthly"][i, j] = cohorts["store_monthly"][i, j - 1] * (1 - cm)

            months_since = j - i
            if months_since > 0 and months_since % 12 == 0:
                ca = min(1.0, base_non_renewal * mult)
                cohorts["web_annual"][i, j] = cohorts["web_annual"][i, j - 1] * (1 - ca)
                cohorts["store_annual"][i, j] = cohorts["store_annual"][i, j - 1] * (1 - ca)
            else:
                cohorts["web_annual"][i, j] = cohorts["web_annual"][i, j - 1]
                cohorts["store_annual"][i, j] = cohorts["store_annual"][i, j - 1]

    # --- Active users by plan ---
    active_w = np.zeros(N)
    active_m_arr = np.zeros(N)
    active_a = np.zeros(N)
    for j in range(N):
        active_w[j] = np.sum(cohorts["web_weekly"][:, j] + cohorts["store_weekly"][:, j])
        active_m_arr[j] = np.sum(cohorts["web_monthly"][:, j] + cohorts["store_monthly"][:, j])
        active_a[j] = np.sum(cohorts["web_annual"][:, j] + cohorts["store_annual"][:, j])

    df["Active Web Users"] = [np.sum(cohorts["web_weekly"][:, j] + cohorts["web_monthly"][:, j] + cohorts["web_annual"][:, j]) for j in range(N)]
    df["Active Store Users"] = [np.sum(cohorts["store_weekly"][:, j] + cohorts["store_monthly"][:, j] + cohorts["store_annual"][:, j]) for j in range(N)]
    df["Total Active Users"] = df["Active Web Users"] + df["Active Store Users"]

    # --- Revenue (per-phase pricing) ---
    gross_rev_web = np.zeros(N)
    gross_rev_store = np.zeros(N)
    mrr_web = np.zeros(N)
    mrr_store = np.zeros(N)
    mrr_weekly_a = np.zeros(N)
    mrr_monthly_a = np.zeros(N)
    mrr_annual_a = np.zeros(N)
    tx_web = np.zeros(N)
    new_mrr_arr = np.zeros(N)

    for j in range(N):
        pw, pm, pa = get_prices(get_phase(j + 1))

        mw_web = np.sum(cohorts["web_weekly"][:, j]) * pw * 4.33
        mm_web = np.sum(cohorts["web_monthly"][:, j]) * pm
        ma_web = np.sum(cohorts["web_annual"][:, j]) * pa / 12.0
        mw_st = np.sum(cohorts["store_weekly"][:, j]) * pw * 4.33
        mm_st = np.sum(cohorts["store_monthly"][:, j]) * pm
        ma_st = np.sum(cohorts["store_annual"][:, j]) * pa / 12.0

        mrr_web[j] = mw_web + mm_web + ma_web
        mrr_store[j] = mw_st + mm_st + ma_st
        mrr_weekly_a[j] = mw_web + mw_st
        mrr_monthly_a[j] = mm_web + mm_st
        mrr_annual_a[j] = ma_web + ma_st

        # New MRR from users acquired this month
        nw_j = df.loc[j, "New Web Users"]
        ns_j = df.loc[j, "New Store Users"]
        phase_j = get_phase(j + 1)
        mw_j, mm_j, ma_j = get_mix(phase_j)
        new_mrr_arr[j] = (nw_j + ns_j) * (mw_j * pw * 4.33 + mm_j * pm + ma_j * pa / 12.0)

        # Cash revenue (annual paid upfront)
        cash_a_web = 0
        cash_a_store = 0
        tx_a = 0
        for i in range(j + 1):
            if (j - i) % 12 == 0:
                cash_a_web += cohorts["web_annual"][i, j] * pa
                cash_a_store += cohorts["store_annual"][i, j] * pa
                tx_a += cohorts["web_annual"][i, j]
        gross_rev_web[j] = mw_web + mm_web + cash_a_web
        gross_rev_store[j] = mw_st + mm_st + cash_a_store
        tx_web[j] = np.sum(cohorts["web_weekly"][:, j]) * 4.33 + np.sum(cohorts["web_monthly"][:, j]) + tx_a

    # Refunds
    rf = 1 - config.refund_rate / 100.0
    gross_rev_web *= rf
    gross_rev_store *= rf

    df["Gross Revenue Web"] = gross_rev_web
    df["Gross Revenue Store"] = gross_rev_store
    df["Total Gross Revenue"] = gross_rev_web + gross_rev_store
    df["MRR Web"] = mrr_web * rf
    df["MRR Store"] = mrr_store * rf
    df["Total MRR"] = df["MRR Web"] + df["MRR Store"]
    df["MRR Weekly"] = mrr_weekly_a * rf
    df["MRR Monthly"] = mrr_monthly_a * rf
    df["MRR Annual"] = mrr_annual_a * rf
    df["Recognized Revenue"] = df["Total MRR"]
    df["New MRR"] = new_mrr_arr * rf

    # --- Expansion / Contraction MRR ---
    expansion_mrr = np.zeros(N)
    contraction_mrr = np.zeros(N)
    for j in range(N):
        pw, pm, pa = get_prices(get_phase(j + 1))
        upgraders = active_m_arr[j] * (config.upgrade_rate / 100.0)
        expansion_mrr[j] = upgraders * abs(pa / 12.0 - pm)
        downgraders = active_a[j] * (config.downgrade_rate / 100.0 / 12.0)
        contraction_mrr[j] = downgraders * abs(pm - pa / 12.0)
    df["Expansion MRR"] = expansion_mrr
    df["Contraction MRR"] = contraction_mrr

    # --- Churned MRR ---
    total_mrr_series = df["Total MRR"].values
    churned_mrr = np.zeros(N)
    for j in range(1, N):
        existing_mrr_now = total_mrr_series[j] - new_mrr_arr[j] * rf
        churned_mrr[j] = max(0, total_mrr_series[j - 1] - existing_mrr_now)
    df["Churned MRR"] = churned_mrr
    df["Net New MRR"] = df["New MRR"] + df["Expansion MRR"] - df["Contraction MRR"] - df["Churned MRR"]

    # --- Commissions ---
    df["Store Commission"] = df["Gross Revenue Store"] * (config.app_store_comm / 100.0)
    df["Web Commission"] = df["Gross Revenue Web"] * (config.web_comm_pct / 100.0) + tx_web * config.web_comm_fixed * rf
    df["Bank Fee"] = df["Total Gross Revenue"] * (config.bank_fee / 100.0)
    df["Total Commissions"] = df["Store Commission"] + df["Web Commission"] + df["Bank Fee"]
    df["Net Revenue"] = df["Total Gross Revenue"] - df["Total Commissions"]

    # --- Costs (per-phase COGS and organic spend) ---
    cogs_per_phase = {1: phase_cfg[1]["cogs"], 2: phase_cfg[2]["cogs"], 3: phase_cfg[3]["cogs"]}
    df["COGS"] = df.apply(lambda r: r["Total Active Users"] * cogs_per_phase[r["Product Phase"]], axis=1)
    org_spend_per_phase = {1: phase_cfg[1]["org_spend"], 2: phase_cfg[2]["org_spend"], 3: phase_cfg[3]["org_spend"]}
    df["Organic Spend"] = df["Product Phase"].map(org_spend_per_phase)
    df["Marketing"] = df["Ad Budget"] + df["Organic Spend"]
    df["Salaries"] = df["Product Phase"].map({1: phase_cfg[1]["sal"], 2: phase_cfg[2]["sal"], 3: phase_cfg[3]["sal"]})
    df["Misc Costs"] = df["Product Phase"].map({1: phase_cfg[1]["misc"], 2: phase_cfg[2]["misc"], 3: phase_cfg[3]["misc"]})
    df["Total Expenses"] = df["COGS"] + df["Marketing"] + df["Salaries"] + df["Misc Costs"]

    # P&L on cash basis
    df["Gross Profit"] = df["Total Gross Revenue"] - df["COGS"] - df["Total Commissions"]
    df["EBITDA"] = df["Gross Profit"] - df["Marketing"] - df["Salaries"] - df["Misc Costs"]
    df["Corporate Tax"] = df["EBITDA"].apply(lambda x: x * (config.corporate_tax / 100.0) if x > 0 else 0)
    df["Net Profit"] = df["EBITDA"] - df["Corporate Tax"]
    df["Net Cash Flow"] = df["Total Gross Revenue"] - df["Total Commissions"] - df["Total Expenses"] - df["Corporate Tax"]
    # Accrual-basis P&L
    df["Recognized Gross Profit"] = df["Recognized Revenue"] - df["COGS"] - df["Total Commissions"]
    df["Recognized EBITDA"] = df["Recognized Gross Profit"] - df["Marketing"] - df["Salaries"] - df["Misc Costs"]

    # Cash Balance with per-phase investments
    total_investment = phase_cfg[1]["inv"] + phase_cfg[2]["inv"] + phase_cfg[3]["inv"]
    cash_bal = np.zeros(N)
    for j in range(N):
        inv = 0
        if j == 0:
            inv = phase_cfg[1]["inv"]
        elif j == p1_end:
            inv = phase_cfg[2]["inv"]
        elif j == p2_end:
            inv = phase_cfg[3]["inv"]
        if j == 0:
            cash_bal[j] = inv + df.loc[j, "Net Cash Flow"]
        else:
            cash_bal[j] = cash_bal[j - 1] + inv + df.loc[j, "Net Cash Flow"]
    df["Cash Balance"] = cash_bal
    df["Deferred Revenue"] = (df["Total Gross Revenue"] - df["Recognized Revenue"]).cumsum()
    df["Cumulative Net Profit"] = df["Net Profit"].cumsum()
    df["Cumulative Revenue"] = df["Total Gross Revenue"].cumsum()
    df["Cumulative Marketing"] = df["Marketing"].cumsum()
    df["Cumulative Ad Spend"] = df["Ad Budget"].cumsum()

    # ===================== METRICS =====================

    df["Paid CAC"] = df["Ad Budget"] / df["Paid New Paid Users"].replace(0, np.nan)
    df["Organic CAC"] = df["Organic Spend"] / df["Organic New Paid Users"].replace(0, np.nan)
    df["Blended CAC"] = df["Marketing"] / df["New Paid Users"].replace(0, np.nan)
    df["ARPU"] = df["Total MRR"] / df["Total Active Users"].replace(0, np.nan)

    # Blended churn
    blended_churn = np.zeros(N)
    for j in range(N):
        phase_j = get_phase(j + 1)
        mult = churn_mult_map[phase_j] * churn_factor
        cw = min(1.0, base_churn_w * mult)
        cm_val = min(1.0, base_churn_m * mult)
        ca_monthly = min(1.0, base_non_renewal * mult) / 12.0
        total = active_w[j] + active_m_arr[j] + active_a[j]
        if total > 0:
            blended_churn[j] = (cw * active_w[j] + cm_val * active_m_arr[j] + ca_monthly * active_a[j]) / total
    df["Blended Churn"] = blended_churn

    # CRR (Customer Retention Rate)
    df["CRR %"] = (1 - df["Blended Churn"]) * 100

    df["Gross Margin %"] = df["Gross Profit"] / df["Total Gross Revenue"].replace(0, np.nan)
    df["LTV"] = (df["ARPU"] * df["Gross Margin %"]) / pd.Series(blended_churn).replace(0, np.nan)
    df["LTV/CAC"] = df["LTV"] / df["Blended CAC"].replace(0, np.nan)
    df["MER"] = df["Total Gross Revenue"] / df["Marketing"].replace(0, np.nan)
    df["Payback Period (Months)"] = df["Blended CAC"] / (df["ARPU"] * df["Gross Margin %"]).replace(0, np.nan)

    # ROI (cumulative)
    total_costs_cum = (df["Total Expenses"] + df["Total Commissions"] + df["Corporate Tax"]).cumsum()
    df["ROI %"] = ((df["Cumulative Revenue"] - total_costs_cum - total_investment) / max(total_investment, 1)) * 100

    # ROAS
    df["ROAS"] = df["Total Gross Revenue"] / df["Ad Budget"].replace(0, np.nan)
    df["Cumulative ROAS"] = df["Cumulative Revenue"] / df["Cumulative Ad Spend"].replace(0, np.nan)

    # NRR
    nrr = np.full(N, np.nan)
    for j in range(1, N):
        if total_mrr_series[j - 1] > 0:
            existing_mrr = total_mrr_series[j] - new_mrr_arr[j] * rf
            nrr[j] = (existing_mrr / total_mrr_series[j - 1]) * 100
    df["NRR %"] = nrr

    # Quick Ratio
    denominator = df["Churned MRR"] + df["Contraction MRR"]
    df["Quick Ratio"] = (df["New MRR"] + df["Expansion MRR"]) / denominator.replace(0, np.nan)

    # Burn Rate & Runway
    df["Burn Rate"] = df["Net Cash Flow"].apply(lambda x: abs(x) if x < 0 else 0)
    runway = np.full(N, np.nan)
    for j in range(N):
        if df.loc[j, "Net Cash Flow"] < 0 and cash_bal[j] > 0:
            runway[j] = cash_bal[j] / abs(df.loc[j, "Net Cash Flow"])
    df["Runway (Months)"] = runway

    # CAE
    df["CAE"] = df["Net New MRR"] / df["Marketing"].replace(0, np.nan)

    # Revenue per Install
    df["Revenue per Install"] = df["Total Gross Revenue"] / df["Installs"].replace(0, np.nan)

    # Churn rates for display
    df["Weekly Churn %"] = [min(100.0, base_churn_w * churn_mult_map[get_phase(m)] * churn_factor * 100) for m in months]
    df["Monthly Churn %"] = [min(100.0, base_churn_m * churn_mult_map[get_phase(m)] * churn_factor * 100) for m in months]
    df["Annual Non-Renewal %"] = [min(100.0, base_non_renewal * churn_mult_map[get_phase(m)] * churn_factor * 100) for m in months]

    # ===================== MILESTONES =====================
    milestones = {}

    be_months = df[df["Net Profit"] > 0]["Month"]
    milestones["break_even_month"] = int(be_months.iloc[0]) if len(be_months) > 0 else None

    cum_be = df[df["Cumulative Net Profit"] > 0]["Month"]
    milestones["cumulative_break_even"] = int(cum_be.iloc[0]) if len(cum_be) > 0 else None

    cf_pos = df[df["Net Cash Flow"] > 0]["Month"]
    milestones["cf_positive_month"] = int(cf_pos.iloc[0]) if len(cf_pos) > 0 else None

    payback = df[df["Cumulative Net Profit"] >= total_investment]["Month"]
    milestones["investment_payback_month"] = int(payback.iloc[0]) if len(payback) > 0 else None

    cash_neg = df[df["Cash Balance"] < 0]["Month"]
    milestones["runway_out_month"] = int(cash_neg.iloc[0]) if len(cash_neg) > 0 else None

    for threshold in [1000, 10000, 100000]:
        um = df[df["Total Active Users"] >= threshold]["Month"]
        milestones[f"users_{threshold}"] = int(um.iloc[0]) if len(um) > 0 else None

    for threshold in [10000, 50000, 100000, 1000000]:
        mm = df[df["Total MRR"] >= threshold]["Month"]
        milestones[f"mrr_{threshold}"] = int(mm.iloc[0]) if len(mm) > 0 else None

    # Cohort retention matrix for heatmap
    cohort_sizes = np.zeros(N)
    retention_matrix = np.zeros((N, N))
    for i in range(N):
        total_cohort_i = sum(cohorts[k][i, i] for k in cohorts)
        cohort_sizes[i] = total_cohort_i
        for j in range(i, N):
            total_remaining = sum(cohorts[k][i, j] for k in cohorts)
            if total_cohort_i > 0:
                retention_matrix[i, j] = total_remaining / total_cohort_i * 100

    return df, milestones, retention_matrix
