"""RelateIQ Streamlit app (Snowflake CoCo CLI Hackathon, PS2).

Author: Ratnesh Saxena. Demo mode reads data/ CSVs; Live mode reads Snowflake
via SNOWFLAKE_* env vars / st.secrets and falls back to demo with a warning.
Deps: streamlit, pandas only.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

import engine

st.set_page_config(page_title="RelateIQ", page_icon=":bar_chart:", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("RelateIQ")
st.sidebar.caption("Arjun Mehta · Relationship Manager")
mode = st.sidebar.radio("Mode", ["Demo", "Live"], index=0,
                        help="Demo reads local data/ files. Live reads Snowflake.")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_live_data() -> dict:
    """Load customers/accounts/txns/repayments/signals from Snowflake.

    Credentials come from SNOWFLAKE_* env vars or st.secrets only.
    Raises on any failure so the caller can fall back to demo.
    """
    import snowflake.connector  # noqa: E402

    def secret(name: str) -> str:
        val = os.environ.get(name)
        if val:
            return val
        try:
            return st.secrets[name]
        except Exception:
            return ""

    conn = snowflake.connector.connect(
        account=secret("SNOWFLAKE_ACCOUNT"),
        user=secret("SNOWFLAKE_USER"),
        password=secret("SNOWFLAKE_PASSWORD"),
        warehouse=secret("SNOWFLAKE_WAREHOUSE"),
        database=secret("SNOWFLAKE_DATABASE") or "RELATEIQ_DEMO",
        schema=secret("SNOWFLAKE_SCHEMA") or "OPS",
    )
    cur = conn.cursor()

    def fetch(table: str) -> list:
        cur.execute(f"SELECT * FROM {table}")
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    customers = fetch("CUSTOMERS")
    accounts = fetch("ACCOUNTS")
    transactions = fetch("TRANSACTIONS")
    repayments = fetch("REPAYMENTS")

    def fetch_md(table: str) -> dict:
        cur.execute(f"SELECT customer_id, transcript_md FROM {table}")
        rows = cur.fetchall()
        out = {}
        for cid, md in rows:
            for s in engine.VALID_SIGNALS:
                if f"[SIGNAL: {s}]" in str(md):
                    out.setdefault(str(cid), []).append(s)
        return out

    t_signals = fetch_md("CALL_TRANSCRIPTS")
    cur.execute("SELECT customer_id, thread_md FROM SUPPORT_EMAILS")
    e_signals = {}
    for cid, md in cur.fetchall():
        for s in engine.VALID_SIGNALS:
            if f"[SIGNAL: {s}]" in str(md):
                e_signals.setdefault(str(cid), []).append(s)
    cur.close()
    conn.close()

    customers_by_id = {str(c.get("customer_id")): c for c in customers}
    return {
        "customers": customers,
        "customers_by_id": customers_by_id,
        "accounts": accounts,
        "accounts_by_customer": engine._index(accounts, "customer_id"),
        "transactions": transactions,
        "txns_by_account": engine._index(transactions, "account_id"),
        "repayments": repayments,
        "repayments_by_account": engine._index(repayments, "account_id"),
        "signals_by_customer": engine._merge_signals(t_signals, e_signals),
        "transcripts": {},
        "emails": {},
    }


@st.cache_data(show_spinner="Loading data...")
def get_data(mode: str) -> tuple:
    """Returns (data_dict, source_label, warning_or_None)."""
    if mode == "Live":
        try:
            return load_live_data(), "Live (Snowflake)", None
        except Exception as exc:  # fall back to demo with a visible warning
            warn = (f"Live mode unavailable ({type(exc).__name__}: {exc}). "
                    "Showing Demo data instead.")
            try:
                return engine.load_demo_data(), "Demo (fallback)", warn
            except FileNotFoundError:
                return engine.demo_fixtures(), "Demo fixtures (fallback)", warn
    try:
        return engine.load_demo_data(), "Demo", None
    except FileNotFoundError:
        return engine.demo_fixtures(), "Demo fixtures", (
            "data/ CSVs not found yet (built in parallel). "
            "Showing tiny inline fixtures so the UI stays usable.")


data, source_label, warning = get_data(mode)
if warning:
    st.warning(warning)
st.sidebar.caption(f"Source: {source_label}")

results = engine.run_pipeline(data)
by_id = {r["customer_id"]: r for r in results}

if "approved" not in st.session_state:
    st.session_state["approved"] = set()

# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------

def _style_map(styler, fn, subset):
    """Elementwise cell styling, pandas-version safe (Styler.map vs applymap)."""
    mapper = getattr(styler, "map", None) or getattr(styler, "applymap")
    return mapper(fn, subset=subset)


def _attention_style(score: int) -> str:
    if score >= 80:
        return "background-color:#c62828;color:white"
    if score >= 60:
        return "background-color:#ef6c00;color:white"
    if score >= 30:
        return "background-color:#f9a825;color:black"
    return "background-color:#2e7d32;color:white"


ACTION_COLORS = {
    "dispute-hold": "#6a1b9a",
    "churn-intervention": "#c62828",
    "collections-firm": "#ef6c00",
    "collections-gentle": "#f9a825",
    "retention-offer": "#1565c0",
    "upsell": "#2e7d32",
    "monitor": "#757575",
}


def action_badge(action: str) -> str:
    color = ACTION_COLORS.get(action, "#757575")
    return (f'<span style="background-color:{color};color:white;'
            f'padding:3px 10px;border-radius:12px;font-size:12px;'
            f'white-space:nowrap">{action}</span>')


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(["Priority Feed", "Customer 360", "Action Queue"])

# ---- Tab 1: Priority Feed ---------------------------------------------------

with tab1:
    st.subheader(f"Priority Feed · {len(results)} customers · as of 2026-10-06")

    bands = [r["band"] for r in results]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Critical (80+)", bands.count("Critical"))
    c2.metric("High (60-79)", bands.count("High"))
    c3.metric("Watch (30-59)", bands.count("Watch"))
    c4.metric("Healthy (<30)", bands.count("Healthy"))

    df = pd.DataFrame([{
        "Customer": f"{r['customer_id']} · {r['name']}",
        "Segment": r["segment"],
        "Attention": r["attention"],
        "Band": r["band"],
        "Next best action": r["action"],
        "Top signal": r["top_signal"],
        "DPD": r["dpd"],
    } for r in results])

    styled = _style_map(df.style, _attention_style, ["Attention"])
    styled = _style_map(
        styled,
        lambda a: (f"background-color:{ACTION_COLORS.get(a, '#757575')};"
                   f"color:white"),
        ["Next best action"],
    )
    st.dataframe(styled, width="stretch", hide_index=True)

    st.markdown("#### Reasoning trace")
    for r in results:
        with st.expander(f"{r['customer_id']} · {r['name']} · "
                         f"attention {r['attention']} · {r['action']}"):
            st.markdown(f"**Reason:** {r['reason']}")
            st.markdown(f"**Top signal:** {r['top_signal']}")
            st.code("\n".join(r["trace"]), language="text")

# ---- Tab 2: Customer 360 ----------------------------------------------------

with tab2:
    st.subheader("Customer 360")
    choice = st.selectbox(
        "Customer",
        options=[r["customer_id"] for r in results],
        format_func=lambda cid: f"{cid} · {by_id[cid]['name']}",
    )
    r = by_id[choice]
    cust = r["cust"]
    st.markdown(f"### {cust.get('name')} "
                f"<small>({cust.get('segment')} · {cust.get('region')})</small>",
                unsafe_allow_html=True)
    st.caption(f"{cust.get('contact_email')} · {cust.get('contact_phone')} · "
               f"profile: {cust.get('behavior_profile')}")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Tenure", f"{cust.get('tenure_months')} mo")
    k2.metric("Credit score", cust.get("credit_score"))
    k3.metric("Utilization", f"{cust.get('utilization_pct')}%")
    k4.metric("DPD", r["dpd"])
    k5.metric("LTV", engine._fmt_inr(float(cust.get("lifetime_value") or 0)))
    k6.metric("Products", cust.get("products_held"))

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("**Accounts**")
        if r["accounts"]:
            st.dataframe(pd.DataFrame(r["accounts"]), width="stretch",
                         hide_index=True)
        else:
            st.info("No accounts on file.")
        st.markdown("**Recent transactions**")
        if r["txns"]:
            tx = pd.DataFrame(r["txns"]).sort_values("txn_date", ascending=False)
            st.dataframe(tx.head(10), width="stretch", hide_index=True)
        else:
            st.info("No transactions in the last 90 days.")
    with c_right:
        st.markdown("**Repayment history**")
        if r["repayments"]:
            rp = pd.DataFrame(r["repayments"]).sort_values("due_date", ascending=False)
            st.dataframe(rp.head(15), width="stretch", hide_index=True)
        else:
            st.info("No repayment records.")
        st.markdown("**Signals**")
        if r["signals"]:
            st.markdown(" ".join(action_badge(s) for s in r["signals"]),
                        unsafe_allow_html=True)
        else:
            st.caption("none")
        for label, store in (("Call transcript", data.get("transcripts", {})),
                             ("Support email", data.get("emails", {}))):
            text = store.get(choice)
            if text:
                with st.expander(label):
                    st.text(text)

    st.markdown("---")
    st.markdown(f"**Recommended action:** {action_badge(r['action'])}",
                unsafe_allow_html=True)
    st.markdown(f"*{r['reason']}*")
    st.text_area("Draft", value=r["draft"], height=260,
                 key=f"draft360_{choice}", disabled=True)

# ---- Tab 3: Action Queue ----------------------------------------------------

with tab3:
    st.subheader("Action Queue")
    st.caption("Approve a draft to write it to the append-only audit log.")

    pending = [r for r in results if r["customer_id"] not in st.session_state["approved"]]
    done = [r for r in results if r["customer_id"] in st.session_state["approved"]]
    st.markdown(f"**{len(pending)} pending** · {len(done)} approved")

    for r in pending:
        cid = r["customer_id"]
        with st.expander(f"{cid} · {r['name']} · att {r['attention']} "
                         f"({r['band']}) · {r['action']}", expanded=False):
            st.markdown(action_badge(r["action"]), unsafe_allow_html=True)
            st.markdown(f"*{r['reason']}*")
            draft = st.text_area("Draft (editable)", value=r["draft"], height=240,
                                 key=f"draftq_{cid}")
            if st.button("Approve", key=f"approve_{cid}"):
                record = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "customer_id": cid,
                    "action": r["action"],
                    "attention": r["attention"],
                    "opportunity": r["opportunity"],
                    "reason": r["reason"],
                }
                path = engine.append_audit(None, record)
                st.session_state["approved"].add(cid)
                st.success(f"Approved. Audit row written to {path}.")
                st.rerun()

    if done:
        with st.expander(f"Approved ({len(done)})", expanded=False):
            for r in done:
                st.markdown(f"{action_badge(r['action'])} **{r['customer_id']}** "
                            f"· {r['name']}", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Audit log** (append-only)")
    audit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "data", "audit_log.csv")
    if os.path.exists(audit_path):
        st.dataframe(pd.read_csv(audit_path), width="stretch",
                     hide_index=True)
    else:
        st.caption("No audit rows yet. Approve an action above to write the first row.")
