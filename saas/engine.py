"""Pure data engine — run_saas_model(config, sens_params) with no Streamlit dependencies."""

import numpy as np
import pandas as pd

from saas.model_config import SaasConfig


def run_saas_model(config: SaasConfig, sens_params: dict | None = None):
    """Run the B2B SaaS financial model. Returns (df, milestones).

    Args:
        config: SaasConfig with all parameters.
        sens_params: dict with keys conv, churn, expansion, organic (fractional, e.g. 0.2 = +20%).
    """
    if sens_params is None:
        sens_params = {"conv": 0, "churn": 0, "expansion": 0, "organic": 0}

    N = config.total_months
    months = np.arange(1, N + 1)
    df = pd.DataFrame({"Month": months})

    conv_factor = 1 + sens_params.get("conv", 0)
    churn_factor = 1 + sens_params.get("churn", 0)
    expansion_factor = 1 + sens_params.get("expansion", 0)
    organic_factor = 1 + sens_params.get("organic", 0)

    p1_end = config.phase1_dur
    p2_end = config.phase1_dur + config.phase2_dur

    def get_phase(m):
        if m <= p1_end:
            return 1
        elif m <= p2_end:
            return 2
        return 3

    df["Phase"] = df["Month"].apply(get_phase)

    phase_cfg = {1: config.phase1, 2: config.phase2, 3: config.phase3}

    # ===================== PIPELINE =====================
    ad_budgets = np.zeros(N)
    cpls = np.zeros(N)
    total_leads = np.zeros(N)
    paid_leads = np.zeros(N)
    organic_leads = np.zeros(N)
    demos = np.zeros(N)
    new_deals = np.zeros(N)
    new_seats = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        ad_budgets[i] = cfg.ad_budget
        cpls[i] = cfg.cpl

        # Paid leads
        if cfg.cpl > 0:
            paid_leads[i] = cfg.ad_budget / cfg.cpl

        # Organic leads as % of total: organic_pct% of total = organic
        # paid = (100 - organic_pct)% of total => total = paid / (1 - organic_pct/100)
        org_pct = min(99.0, cfg.organic_leads_pct * organic_factor)
        if org_pct > 0 and org_pct < 100:
            total_from_paid = paid_leads[i] / max(0.01, (1 - org_pct / 100.0))
            organic_leads[i] = total_from_paid - paid_leads[i]

        total_leads[i] = paid_leads[i] + organic_leads[i]

        # Demo conversion
        lead_to_demo = cfg.lead_to_demo / 100.0 * conv_factor
        demos[i] = total_leads[i] * lead_to_demo

        # Deal closing (with sales cycle delay)
        demo_to_close = cfg.demo_to_close / 100.0 * conv_factor
        delay = cfg.sales_cycle_months
        if i >= delay:
            # Use demos from `delay` months ago
            demos_for_close = demos[i - delay] if delay > 0 else demos[i]
        else:
            demos_for_close = demos[i] if delay == 0 else 0

        new_deals[i] = demos_for_close * demo_to_close
        new_seats[i] = new_deals[i] * cfg.seats_per_account

    df["Ad Budget"] = ad_budgets
    df["CPL"] = cpls
    df["Paid Leads"] = paid_leads
    df["Organic Leads"] = organic_leads
    df["Total Leads"] = total_leads
    df["Demos"] = demos
    df["New Deals"] = new_deals
    df["New Seats"] = new_seats

    # ===================== CUSTOMER & SEAT TRACKING =====================
    active_customers = np.zeros(N)
    active_seats = np.zeros(N)
    churned_customers = np.zeros(N)
    expansion_seats = np.zeros(N)
    contraction_seats = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        if i == 0:
            prev_customers = config.initial_customers
            prev_seats = config.initial_seats
        else:
            prev_customers = active_customers[i - 1]
            prev_seats = active_seats[i - 1]

        # Churn (logo churn)
        churn_rate = cfg.logo_churn_rate / 100.0 * churn_factor
        churned = prev_customers * churn_rate
        churned_customers[i] = churned

        # Seats lost from churned customers (proportional)
        if prev_customers > 0:
            seats_per_customer = prev_seats / prev_customers
        else:
            seats_per_customer = cfg.seats_per_account
        churned_seats = churned * seats_per_customer

        # Expansion & contraction on remaining customers
        remaining_customers = prev_customers - churned
        remaining_seats = prev_seats - churned_seats

        exp_rate = cfg.expansion_rate / 100.0 * expansion_factor
        con_rate = cfg.contraction_rate / 100.0
        expansion_seats[i] = remaining_seats * exp_rate
        contraction_seats[i] = remaining_seats * con_rate

        active_customers[i] = max(0, remaining_customers + new_deals[i])
        active_seats[i] = max(0, remaining_seats + new_seats[i] + expansion_seats[i] - contraction_seats[i])

    df["Active Customers"] = active_customers
    df["Active Seats"] = active_seats
    df["Churned Customers"] = churned_customers
    df["Expansion Seats"] = expansion_seats
    df["Contraction Seats"] = contraction_seats

    # ===================== MRR & ARR =====================
    monthly_mrr = np.zeros(N)
    annual_mrr = np.zeros(N)
    total_mrr = np.zeros(N)
    arr = np.zeros(N)
    new_mrr = np.zeros(N)
    expansion_mrr = np.zeros(N)
    contraction_mrr = np.zeros(N)
    churned_mrr = np.zeros(N)
    net_new_mrr = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        price = cfg.price_per_seat
        annual_pct = cfg.annual_contract_pct / 100.0
        monthly_pct = 1.0 - annual_pct
        discount = cfg.annual_discount / 100.0

        # Monthly-contract seats pay full price; annual-contract seats pay discounted
        monthly_seats = active_seats[i] * monthly_pct
        annual_seats = active_seats[i] * annual_pct

        monthly_mrr[i] = monthly_seats * price
        annual_mrr[i] = annual_seats * price * (1 - discount)
        total_mrr[i] = monthly_mrr[i] + annual_mrr[i]
        arr[i] = total_mrr[i] * 12

        # MRR movements
        new_mrr[i] = new_seats[i] * price * (monthly_pct + annual_pct * (1 - discount))
        expansion_mrr[i] = expansion_seats[i] * price * (monthly_pct + annual_pct * (1 - discount))
        contraction_mrr[i] = contraction_seats[i] * price * (monthly_pct + annual_pct * (1 - discount))

        if i == 0:
            prev_customers = config.initial_customers
            prev_seats = config.initial_seats
        else:
            prev_customers = active_customers[i - 1]
            prev_seats = active_seats[i - 1]

        if prev_customers > 0:
            seats_per_customer = prev_seats / prev_customers
        else:
            seats_per_customer = cfg.seats_per_account
        churned_mrr[i] = churned_customers[i] * seats_per_customer * price * (monthly_pct + annual_pct * (1 - discount))

        net_new_mrr[i] = new_mrr[i] + expansion_mrr[i] - contraction_mrr[i] - churned_mrr[i]

    df["Monthly MRR"] = monthly_mrr
    df["Annual MRR"] = annual_mrr
    df["Total MRR"] = total_mrr
    df["ARR"] = arr
    df["New MRR"] = new_mrr
    df["Expansion MRR"] = expansion_mrr
    df["Contraction MRR"] = contraction_mrr
    df["Churned MRR"] = churned_mrr
    df["Net New MRR"] = net_new_mrr

    # ===================== REVENUE & COGS =====================
    gross_revenue = total_mrr.copy()
    cogs = np.zeros(N)
    gross_profit = np.zeros(N)
    gross_margin_pct = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]
        cogs[i] = active_seats[i] * cfg.cogs_per_seat
        gross_profit[i] = gross_revenue[i] - cogs[i]
        if gross_revenue[i] > 0:
            gross_margin_pct[i] = gross_profit[i] / gross_revenue[i] * 100
        else:
            gross_margin_pct[i] = 0

    df["Gross Revenue"] = gross_revenue
    df["COGS"] = cogs
    df["Gross Profit"] = gross_profit
    df["Gross Margin %"] = gross_margin_pct

    # ===================== OPEX =====================
    salaries = np.zeros(N)
    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]
        salaries[i] = cfg.monthly_salary

    df["Marketing"] = ad_budgets
    df["Salaries"] = salaries
    df["Misc Costs"] = config.misc_costs
    df["Total Expenses"] = df["COGS"] + df["Marketing"] + df["Salaries"] + df["Misc Costs"]

    # ===================== P&L =====================
    df["EBITDA"] = df["Gross Revenue"] - df["COGS"] - df["Marketing"] - df["Salaries"] - df["Misc Costs"]
    df["Corporate Tax"] = df["Gross Revenue"] * (config.corporate_tax / 100.0)
    df["Net Profit"] = df["EBITDA"] - df["Corporate Tax"]
    df["Net Cash Flow"] = df["Net Profit"]

    # Cash balance with initial investment
    cash_flow = df["Net Cash Flow"].values.copy()
    cash_bal = np.zeros(N)
    cash_bal[0] = config.investment + cash_flow[0]
    for i in range(1, N):
        cash_bal[i] = cash_bal[i - 1] + cash_flow[i]
    df["Cash Balance"] = cash_bal

    df["Cumulative Net Profit"] = df["Net Profit"].cumsum()
    df["Cumulative Revenue"] = df["Gross Revenue"].cumsum()
    df["Cumulative Marketing"] = df["Marketing"].cumsum()

    # ===================== UNIT ECONOMICS =====================
    # CAC = Total acquisition cost / new deals
    df["CAC"] = np.where(new_deals > 0, ad_budgets / new_deals, np.nan)

    # LTV = ARPA * Gross Margin% / logo_churn_rate
    ltv = np.zeros(N)
    arpa = np.zeros(N)
    ltv_cac = np.zeros(N)

    for i in range(N):
        phase = get_phase(i + 1)
        cfg = phase_cfg[phase]

        if active_customers[i] > 0:
            arpa[i] = total_mrr[i] / active_customers[i]
        else:
            arpa[i] = 0

        churn_rate = cfg.logo_churn_rate / 100.0 * churn_factor
        gm = gross_margin_pct[i] / 100.0

        if churn_rate > 0:
            ltv[i] = arpa[i] * gm / churn_rate
        else:
            ltv[i] = arpa[i] * gm * 120  # cap at 10 years

        cac_val = df.loc[i, "CAC"]
        if not np.isnan(cac_val) and cac_val > 0:
            ltv_cac[i] = ltv[i] / cac_val
        else:
            ltv_cac[i] = np.nan

    df["ARPA"] = arpa
    df["LTV"] = ltv
    df["LTV/CAC"] = ltv_cac

    # ===================== SaaS METRICS =====================

    # NRR% = (MRR_end - new_mrr) / MRR_start * 100
    nrr_pct = np.full(N, np.nan)
    grr_pct = np.full(N, np.nan)
    quick_ratio = np.full(N, np.nan)

    for i in range(1, N):
        mrr_start = total_mrr[i - 1]
        if mrr_start > 0:
            # NRR: existing revenue including expansion/contraction/churn
            nrr_pct[i] = (mrr_start + expansion_mrr[i] - contraction_mrr[i] - churned_mrr[i]) / mrr_start * 100
            # GRR: existing revenue with only contraction/churn (no expansion)
            grr_pct[i] = (mrr_start - contraction_mrr[i] - churned_mrr[i]) / mrr_start * 100

        # Quick Ratio = (New + Expansion) / (Contraction + Churn)
        denominator = contraction_mrr[i] + churned_mrr[i]
        if denominator > 0:
            quick_ratio[i] = (new_mrr[i] + expansion_mrr[i]) / denominator

    df["NRR %"] = nrr_pct
    df["GRR %"] = grr_pct
    df["Quick Ratio"] = quick_ratio

    # Rule of 40: Revenue growth% + EBITDA margin%
    rule_of_40 = np.full(N, np.nan)
    for i in range(1, N):
        if gross_revenue[i - 1] > 0 and gross_revenue[i] > 0:
            rev_growth = (gross_revenue[i] - gross_revenue[i - 1]) / gross_revenue[i - 1] * 100
            ebitda_margin = df.loc[i, "EBITDA"] / gross_revenue[i] * 100
            rule_of_40[i] = rev_growth + ebitda_margin
    df["Rule of 40"] = rule_of_40

    # Magic Number = Net New ARR (quarter) / Sales & Marketing (prior quarter)
    magic_number = np.full(N, np.nan)
    for i in range(3, N):
        new_arr_q = (arr[i] - arr[i - 3])
        mktg_prior_q = ad_budgets[i - 3] + ad_budgets[i - 2] + ad_budgets[i - 1]
        if mktg_prior_q > 0:
            magic_number[i] = new_arr_q / mktg_prior_q
    df["Magic Number"] = magic_number

    # Burn Rate & Runway
    df["Burn Rate"] = df["Net Cash Flow"].apply(lambda x: abs(x) if x < 0 else 0)
    runway = np.full(N, np.nan)
    for j in range(N):
        if df.loc[j, "Net Cash Flow"] < 0 and cash_bal[j] > 0:
            runway[j] = cash_bal[j] / abs(df.loc[j, "Net Cash Flow"])
    df["Runway (Months)"] = runway

    # Organic %
    df["Organic %"] = np.where(total_leads > 0, organic_leads / total_leads * 100, 0)

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

    for threshold in [50, 100, 500]:
        cm = df[df["Active Customers"] >= threshold]["Month"]
        milestones[f"customers_{threshold}"] = int(cm.iloc[0]) if len(cm) > 0 else None

    for threshold in [100000, 500000, 1000000]:
        am = df[df["ARR"] >= threshold]["Month"]
        milestones[f"arr_{threshold}"] = int(am.iloc[0]) if len(am) > 0 else None

    for threshold in [1000, 5000]:
        sm = df[df["Active Seats"] >= threshold]["Month"]
        milestones[f"seats_{threshold}"] = int(sm.iloc[0]) if len(sm) > 0 else None

    return df, milestones
