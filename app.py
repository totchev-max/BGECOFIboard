import streamlit as st

if "history" not in st.session_state:
    st.session_state.history = []

if "initialized" not in st.session_state:
    st.session_state.initialized = Trueimport os
from dataclasses import dataclass
from datetime import datetime
import streamlit as st

# Optional AI (works only if OPENAI_API_KEY is set)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="Национален финансов борд (DEMO)",
    layout="wide",
)

# -----------------------------
# Helpers / Models
# -----------------------------
@dataclass
class Goals:
    max_deficit_pct: float = 0.03   # 3%
    max_debt_pct: float = 0.60      # 60%
    max_spend_pct: float = 0.40     # 40%
    infl_low: float = 0.02          # 2%
    infl_high: float = 0.04         # 4%
    unemp_attention: float = 0.06   # 6%
    aic_gap_target: float = 25.0    # points gap (EU=100)

@dataclass
class Scenario:
    key: str
    title: str
    affected: str
    kind: str  # "spend" or "rev"

SCENARIOS = [
    Scenario(
        key="NONE",
        title="Без сценарий (референтен бюджет)",
        affected="—",
        kind="none",
    ),
    Scenario(
        key="ADM_WAGES_10",
        title="+10% заплати в администрацията",
        affected="Разходи за персонал (общо)",
        kind="spend",
    ),
    Scenario(
        key="MIN_PENSION_UP",
        title="Увеличение на минималната пенсия",
        affected="Пенсии (общо)",
        kind="spend",
    ),
    Scenario(
        key="MON_WAGES_10",
        title="+10% заплати в МОН",
        affected="Разходи за персонал (МОН)",
        kind="spend",
    ),
    Scenario(
        key="VAT_20_TO_22",
        title="ДДС 20% → 22%",
        affected="Приходи от ДДС (общо)",
        kind="rev",
    ),
]

def eur_bn(x: float) -> str:
    return f"{x:.2f} млрд. €"

def pct(x: float) -> str:
    return f"{x*100:.2f}%"

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def light(val: float, green_th: float, yellow_th: float) -> str:
    if val <= green_th:
        return "🟢"
    if val <= yellow_th:
        return "🟡"
    return "🔴"

def compute_budget_kpis(base: dict, scenario_key: str) -> dict:
    """
    base keys (all in EUR bn unless pct):
      gdp_bn, debt_bn, revenues_bn, expenditures_bn,
      vat_bn, pensions_bn, payroll_total_bn, mon_payroll_bn
    Returns: dict with updated revenues/expenditures/deficit/debt ratios etc.
    """
    gdp = float(base["gdp_bn"])
    debt = float(base["debt_bn"])

    rev = float(base["revenues_bn"])
    exp = float(base["expenditures_bn"])

    vat = float(base["vat_bn"])
    pensions = float(base["pensions_bn"])
    payroll_total = float(base["payroll_total_bn"])
    mon_payroll = float(base["mon_payroll_bn"])

    note = "Референтен DEMO бюджет."

    # DEMO – direct effects only (no second-round macro)
    if scenario_key == "ADM_WAGES_10":
        delta = payroll_total * 0.10
        exp += delta
        note = "DEMO: +10% заплати в администрацията → директен разходен ефект."
    elif scenario_key == "MIN_PENSION_UP":
        # Choose a clean DEMO parameter: +8% on pensions as "min pension uplift proxy"
        # (kept simple and transparent; can be tuned later)
        delta = pensions * 0.08
        exp += delta
        note = "DEMO: увеличение на минималната пенсия (прокси: +8% към пенсии) → директен разходен ефект."
    elif scenario_key == "MON_WAGES_10":
        delta = mon_payroll * 0.10
        exp += delta
        note = "DEMO: +10% заплати в МОН → директен разходен ефект."
    elif scenario_key == "VAT_20_TO_22":
        # Very strict: direct mechanical uplift on VAT revenue only
        # 20% -> 22% implies +10% on VAT receipts if base unchanged (22/20 = 1.10)
        new_vat = vat * (22.0 / 20.0)
        delta = new_vat - vat
        rev += delta
        note = "DEMO: ДДС 20%→22% → директен приходен ефект върху ДДС при фиксирана база (без поведенчески реакции)."

    deficit_bn = exp - rev
    deficit_pct = deficit_bn / gdp if gdp else 0.0
    debt_pct = debt / gdp if gdp else 0.0
    spend_pct = exp / gdp if gdp else 0.0

    return {
        "gdp_bn": gdp,
        "debt_bn": debt,
        "revenues_bn": rev,
        "expenditures_bn": exp,
        "deficit_bn": deficit_bn,
        "deficit_pct": deficit_pct,
        "debt_pct": debt_pct,
        "spend_pct": spend_pct,
        "note": note,
    }

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        # Streamlit secrets support
        api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key or OpenAI is None:
        return None
    return OpenAI(api_key=api_key)

def ai_analyze(payload: dict, question: str) -> str:
    """
    Uses OpenAI if available; otherwise returns a deterministic demo analysis.
    """
    goals: Goals = payload["goals"]
    macro = payload["macro"]
    budget = payload["budget"]
    scenario = payload["scenario_title"]

    # Fallback (no key): deterministic structured output
    client = get_openai_client()
    if client is None:
        # Simple rule-based analysis (still structured & safe)
        lines = []
        lines.append("**Накратко:** Показателите се оценяват спрямо избраната аналитична рамка и активния DEMO сценарий (ако има).")
        lines.append("")
        lines.append("**Какво показват индикаторите:**")
        lines.append(f"- Инфлация (DEMO): {macro['inflation_pct']:.1f}%")
        lines.append(f"- Растеж (DEMO): {macro['growth_pct']:.1f}%")
        lines.append(f"- Безработица (DEMO): {macro['unemployment_pct']:.1f}%")
        lines.append(f"- AIC (EU=100, DEMO): {macro['aic_bg']:.0f} (gap {max(0, 100-macro['aic_bg']):.0f} пункта)")
        lines.append(f"- Дефицит (DEMO бюджет): {pct(budget['deficit_pct'])} | Дълг: {pct(budget['debt_pct'])} | Разходи/БВП: {pct(budget['spend_pct'])}")
        lines.append("")
        lines.append("**Анализ и оптимизация:**")
        lines.append(f"- Рамка: дефицит ≤ {goals.max_deficit_pct*100:.1f}%, дълг ≤ {goals.max_debt_pct*100:.0f}%, разходи ≤ {goals.max_spend_pct*100:.0f}%.")
        if scenario != "Без сценарий (референтен бюджет)":
            lines.append(f"- Активен сценарий: **{scenario}** (директен ефект; без вторични реакции).")
        lines.append("- „Оптимизация“ тук означава балансиране на рискове и цели при фиксирани допускания, без предписания.")
        lines.append("")
        lines.append("**Рискове и чувствителни зони:**")
        # Use simple traffic logic
        def_light = light(abs(budget["deficit_pct"]), goals.max_deficit_pct, goals.max_deficit_pct*1.5)
        debt_light = light(budget["debt_pct"], goals.max_debt_pct, goals.max_debt_pct+0.10)
        spend_light = light(budget["spend_pct"], goals.max_spend_pct, goals.max_spend_pct+0.05)
        lines.append(f"- Дефицит: {def_light} | Дълг: {debt_light} | Разходи: {spend_light}")
        lines.append("- Резултатите са чувствителни към допусканията в DEMO бюджета и избрания сценарий.")
        lines.append("")
        lines.append("**Какво да се следи:**")
        lines.append("- Траектория на дефицита и разходния натиск при различни сценарии.")
        lines.append("- Инфлация и реални доходи (покупателна способност) спрямо догонването по AIC.")
        if question.strip():
            lines.append("")
            lines.append(f"**Въпрос:** {question.strip()}")
            lines.append("*Бележка: В DEMO режим отговорът е ориентационен и не използва външни източници в реално време.*")
        return "\n".join(lines)

    # OpenAI path
    model = os.getenv("OPENAI_MODEL", "") or st.secrets.get("OPENAI_MODEL", "") or "gpt-4.1-mini"

    system = (
        "Ти си „Национален финансов борд“ — публична платформа за икономическо наблюдение, анализ и оптимизация. "
        "Говориш само на български, институционално и неутрално. "
        "Нямаш право да даваш предписания („трябва“, „необходимо е“) или политически препоръки. "
        "Не измисляш факти. Ако данните са DEMO/условни — казваш го. "
        "Отговорът винаги е структуриран: "
        "1) Накратко; 2) Какво показват индикаторите; 3) Анализ и оптимизация; 4) Рискове и чувствителни зони; 5) Какво да се следи."
    )

    user = {
        "macro_snapshot": macro,
        "budget_snapshot": budget,
        "goals": goals.__dict__,
        "scenario": scenario,
        "question": question.strip(),
        "demo_note": "Всички бюджетни числа и сценарии са DEMO, с директен фискален ефект и без вторични икономически реакции."
    }

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": str(user)},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content
  # -----------------------------
# DEMO DATA (macro + budget)
# -----------------------------
DEMO_MACRO = {
    "inflation_pct": 2.9,      # %
    "growth_pct": 2.6,         # %
    "unemployment_pct": 4.2,   # %
    "aic_bg": 78.0,            # EU=100
}

DEMO_BUDGET_BASE = {
    # GDP & debt
    "gdp_bn": 95.0,
    "debt_bn": 30.0,

    # Aggregates
    "revenues_bn": 47.0,
    "expenditures_bn": 49.5,

    # Key lines
    "vat_bn": 16.0,
    "pensions_bn": 12.5,
    "payroll_total_bn": 9.0,
    "mon_payroll_bn": 2.2,
}

# -----------------------------
# Session state
# -----------------------------
if "goals" not in st.session_state:
    st.session_state.goals = Goals()

if "scenario_key" not in st.session_state:
    st.session_state.scenario_key = "NONE"

if "show_goals" not in st.session_state:
    st.session_state.show_goals = False

if "show_scenarios" not in st.session_state:
    st.session_state.show_scenarios = False

# -----------------------------
# Header
# -----------------------------
col_title, col_status = st.columns([3, 2])
with col_title:
    st.markdown("## Национален финансов борд")
    st.caption("Текущо състояние на икономиката (snapshot)")

with col_status:
    st.markdown(
        f"**DEMO** • Последно обновяване: {datetime.now().strftime('%d.%m.%Y')}"
    )
    st.markdown(
        f"**Рамка:** {'Персонализирана рамка: активна' if st.session_state.show_goals else 'Референтна рамка (DEMO)'}"
    )

# -----------------------------
# Top bar actions
# -----------------------------
col_left, col_right = st.columns([3, 2])

with col_left:
    if st.button("Цели и ограничения", use_container_width=True):
        st.session_state.show_goals = not st.session_state.show_goals

with col_right:
    current_scn = next(s for s in SCENARIOS if s.key == st.session_state.scenario_key)
    if st.button(f"Сценарий (DEMO): {current_scn.title} ▾", use_container_width=True):
        st.session_state.show_scenarios = not st.session_state.show_scenarios

# -----------------------------
# Goals overlay (inline panel)
# -----------------------------
if st.session_state.show_goals:
    st.markdown("---")
    st.subheader("Цели и ограничения (DEMO)")
    st.caption("Референтна рамка за анализ и оптимизация. Промяната важи само за тази сесия.")

    g = st.session_state.goals

    c1, c2, c3 = st.columns(3)
    with c1:
        g.max_deficit_pct = st.slider("Макс. дефицит (% БВП)", 0.0, 0.06, g.max_deficit_pct, 0.005)
        g.max_debt_pct = st.slider("Макс. дълг (% БВП)", 0.20, 0.90, g.max_debt_pct, 0.05)
    with c2:
        g.max_spend_pct = st.slider("Макс. разходи (% БВП)", 0.30, 0.55, g.max_spend_pct, 0.05)
        g.unemp_attention = st.slider("Безработица – праг (%)", 0.03, 0.10, g.unemp_attention, 0.005)
    with c3:
        g.infl_low = st.slider("Инфлация – долна граница (%)", 0.00, 0.05, g.infl_low, 0.005)
        g.infl_high = st.slider("Инфлация – горна граница (%)", 0.01, 0.08, g.infl_high, 0.005)
        g.aic_gap_target = st.slider("AIC gap цел (пункта)", 10.0, 40.0, g.aic_gap_target, 1.0)

    st.info("Целите служат като аналитична рамка. Промяната им не представлява решение или препоръка.")

# -----------------------------
# Scenarios overlay (inline panel)
# -----------------------------
if st.session_state.show_scenarios:
    st.markdown("---")
    st.subheader("Бюджетни сценарии (DEMO)")
    st.caption("Тестове на чувствителност с директен фискален ефект.")

    options = {s.title: s.key for s in SCENARIOS}
    selected_title = st.radio(
        "Избери сценарий (само един):",
        list(options.keys()),
        index=list(options.values()).index(st.session_state.scenario_key),
    )
    st.session_state.scenario_key = options[selected_title]

    scn = next(s for s in SCENARIOS if s.key == st.session_state.scenario_key)
    st.write(f"**Засегнати агрегати:** {scn.affected}")
    st.caption("Показан е директният бюджетен ефект. Вторични икономически реакции не са включени.")

# -----------------------------
# Compute KPIs with scenario
# -----------------------------
budget_kpis = compute_budget_kpis(DEMO_BUDGET_BASE, st.session_state.scenario_key)

# -----------------------------
# KPI Cockpit
# -----------------------------
st.markdown("---")
st.subheader("Кокпит – ключови показатели")

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric("Инфлация", f"{DEMO_MACRO['inflation_pct']:.1f}%")
with k2:
    st.metric("Растеж", f"{DEMO_MACRO['growth_pct']:.1f}%")
with k3:
    st.metric("Безработица", f"{DEMO_MACRO['unemployment_pct']:.1f}%")
with k4:
    st.metric("AIC (EU=100)", f"{DEMO_MACRO['aic_bg']:.0f}")

k5, k6, k7, k8 = st.columns(4)

with k5:
    st.metric("Приходи", eur_bn(budget_kpis["revenues_bn"]))
with k6:
    st.metric("Разходи", eur_bn(budget_kpis["expenditures_bn"]))
with k7:
    st.metric("Дефицит", eur_bn(budget_kpis["deficit_bn"]))
with k8:
    st.metric("Дълг (% БВП)", pct(budget_kpis["debt_pct"]))

# -----------------------------
# Traffic lights vs goals
# -----------------------------
g = st.session_state.goals
cA, cB, cC = st.columns(3)

with cA:
    st.write("**Дефицит**", light(abs(budget_kpis["deficit_pct"]), g.max_deficit_pct, g.max_deficit_pct*1.5))
with cB:
    st.write("**Дълг**", light(budget_kpis["debt_pct"], g.max_debt_pct, g.max_debt_pct+0.10))
with cC:
    st.write("**Разходи/БВП**", light(budget_kpis["spend_pct"], g.max_spend_pct, g.max_spend_pct+0.05))

st.caption(budget_kpis["note"])
# -----------------------------
# AI Panel
# -----------------------------
st.markdown("---")
st.subheader("AI анализ")

question = st.text_area(
    "Задай въпрос (по желание). Ако няма въпрос, системата генерира кратък анализ на текущото състояние.",
    height=90,
    placeholder="Напр. „Какво е най-чувствителното спрямо целите при активния сценарий?“",
)

col_run, col_hint = st.columns([1, 2])
with col_run:
    run = st.button("Анализирай", use_container_width=True)
with col_hint:
    st.caption(
        "Бележка: DEMO режим — бюджетът и сценариите са фиктивни. "
        "„Оптимизация“ означава аналитично балансиране спрямо цели, без предписания."
    )

if run:
    payload = {
        "goals": st.session_state.goals,
        "macro": DEMO_MACRO,
        "budget": budget_kpis,
        "scenario_title": next(s for s in SCENARIOS if s.key == st.session_state.scenario_key).title,
    }
    with st.spinner("Генерирам анализ..."):
        try:
            out = ai_analyze(payload, question)
            st.markdown(out)
        except Exception as e:
            st.error("❌ AI повикването не мина.")
            st.code(str(e))

# -----------------------------
# Sources (demo)
# -----------------------------
with st.expander("Провери източници (DEMO)"):
    st.markdown(
        """
Това е **демонстрационна версия**. В LIVE етап индикаторите могат да се свържат към официални институции (напр. НСИ, БНБ, Евростат).
В DEMO режим стойностите са фиктивни и служат за показване на логиката на системата.
"""
    )

# -----------------------------
# Footer
# -----------------------------
st.markdown("---")
st.caption(
    "Национален финансов борд — публична платформа за икономическо наблюдение, анализ и оптимизация (DEMO). "
    "Промяната на цели/сценарии е аналитична рамка и не представлява решение или препоръка."
  )
