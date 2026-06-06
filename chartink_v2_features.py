import streamlit as st
import pandas as pd
import time
from datetime import datetime

# ==========================================================
# CHARTINK V2 FEATURES MODULE
# ==========================================================

def render_v2_filter_panel():

    st.subheader("⚡ Chartink V2 Advanced Filters")

    col1, col2, col3 = st.columns(3)

    # ======================================================
    # CURRENT RSI FILTER
    # ======================================================

    with col1:

        st.markdown("### Current RSI")

        enable_rsi = st.toggle(
            "Enable RSI Filter",
            value=True,
            key="enable_rsi"
        )

        rsi_min = st.number_input(
            "RSI Min",
            min_value=0.0,
            max_value=100.0,
            value=60.0,
            step=1.0,
            key="rsi_min"
        )

        rsi_max = st.number_input(
            "RSI Max",
            min_value=0.0,
            max_value=100.0,
            value=65.0,
            step=1.0,
            key="rsi_max"
        )

    # ======================================================
    # HISTORICAL RSI FILTER
    # ======================================================

    with col2:

        st.markdown("### Historical RSI")

        enable_hist_rsi = st.toggle(
            "Enable Historical RSI",
            value=True,
            key="enable_hist_rsi"
        )

        n_weeks_ago = st.number_input(
            "Weeks Ago",
            min_value=1,
            max_value=52,
            value=4,
            step=1,
            key="n_weeks_ago"
        )

        hist_rsi_min = st.number_input(
            "Historical RSI Min",
            min_value=0.0,
            max_value=100.0,
            value=40.0,
            step=1.0,
            key="hist_rsi_min"
        )

        hist_rsi_max = st.number_input(
            "Historical RSI Max",
            min_value=0.0,
            max_value=100.0,
            value=60.0,
            step=1.0,
            key="hist_rsi_max"
        )

    # ======================================================
    # MARKET CAP FILTER
    # ======================================================

    with col3:

        st.markdown("### Market Cap")

        enable_mcap = st.toggle(
            "Enable Market Cap Filter",
            value=True,
            key="enable_mcap"
        )

        mcap_min = st.number_input(
            "Market Cap Min (Cr)",
            min_value=0,
            value=1000,
            step=1000,
            key="mcap_min"
        )

        mcap_max = st.number_input(
            "Market Cap Max (Cr)",
            min_value=0,
            value=50000,
            step=1000,
            key="mcap_max"
        )

    return {
        "enable_rsi": enable_rsi,
        "rsi_min": rsi_min,
        "rsi_max": rsi_max,

        "enable_hist_rsi": enable_hist_rsi,
        "hist_rsi_min": hist_rsi_min,
        "hist_rsi_max": hist_rsi_max,
        "n_weeks_ago": n_weeks_ago,

        "enable_mcap": enable_mcap,
        "mcap_min": mcap_min,
        "mcap_max": mcap_max
    }


# ==========================================================
# SEARCH BOX
# ==========================================================

def render_search_box():

    return st.text_input(
        "🔍 Search Stock",
        placeholder="Example: SBIN, BEL, TATAMOTORS"
    )


# ==========================================================
# FULL NIFTY500 SCAN OPTION
# ==========================================================

def render_scan_options():

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:

        full_scan = st.checkbox(
            "🚀 Scan Complete Nifty500",
            value=False
        )

    with col2:

        batch_limit = st.slider(
            "Batch Size",
            min_value=25,
            max_value=500,
            value=100,
            step=25
        )

    return full_scan, batch_limit


# ==========================================================
# FILTER ENGINE
# ==========================================================

def validate_filters(
    item,
    filters
):

    current_rsi = item["Current Weekly RSI"]

    historical_rsi = item.get(
        f"{filters['n_weeks_ago']} Wks Ago RSI"
    )

    market_cap = item["Market Cap (Cr)"]

    pass_current_rsi = True
    pass_historical_rsi = True
    pass_market_cap = True

    # RSI RANGE

    if filters["enable_rsi"]:

        pass_current_rsi = (
            filters["rsi_min"]
            <= current_rsi
            <= filters["rsi_max"]
        )

    # HIST RSI RANGE

    if filters["enable_hist_rsi"]:

        if historical_rsi is None:

            pass_historical_rsi = False

        else:

            pass_historical_rsi = (
                filters["hist_rsi_min"]
                <= historical_rsi
                <= filters["hist_rsi_max"]
            )

    # MARKET CAP RANGE

    if filters["enable_mcap"]:

        pass_market_cap = (
            filters["mcap_min"]
            <= market_cap
            <= filters["mcap_max"]
        )

    return (
        pass_current_rsi
        and pass_historical_rsi
        and pass_market_cap
    )


# ==========================================================
# TRADINGVIEW LINK ENGINE
# ==========================================================

def add_tradingview_links(df):

    if df.empty:
        return df

    df["TradingView"] = df["Stock"].apply(
        lambda x:
        f"https://www.tradingview.com/chart/?symbol=NSE:{x}"
    )

    return df


# ==========================================================
# SEARCH FILTER ENGINE
# ==========================================================

def apply_search_filter(
    df,
    search_text
):

    if df.empty:
        return df

    if not search_text:
        return df

    search_text = search_text.upper()

    return df[
        df["Stock"]
        .astype(str)
        .str.upper()
        .str.contains(search_text)
    ]


# ==========================================================
# CSV EXPORT
# ==========================================================

def render_csv_export(df):

    if df.empty:
        return

    csv_data = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="📥 Export Scanner Results",
        data=csv_data,
        file_name=f"scanner_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


# ==========================================================
# AUTO REFRESH ENGINE
# ==========================================================

def render_auto_refresh():

    auto_refresh = st.checkbox(
        "🔄 Auto Refresh (60 sec)",
        value=False
    )

    if auto_refresh:

        st.info(
            "Auto Refresh Enabled"
        )

        time.sleep(60)

        st.rerun()


# ==========================================================
# RESULT FORMATTER
# ==========================================================

def format_scanner_results(df):

    if df.empty:
        return df

    df = df.copy()

    if "Current Weekly RSI" in df.columns:

        df["Current Weekly RSI"] = (
            df["Current Weekly RSI"]
            .round(2)
        )

    if "Market Cap (Cr)" in df.columns:

        df["Market Cap (Cr)"] = (
            df["Market Cap (Cr)"]
            .round(2)
        )

    return df


# ==========================================================
# RESULT TABLE
# ==========================================================

def render_results_table(df):

    if df.empty:

        st.warning(
            "No stocks matched filters."
        )

        return

    st.success(
        f"{len(df)} stocks matched."
    )

    st.dataframe(
        df,
        use_container_width=True
    )


# ==========================================================
# TRADINGVIEW BUTTON TABLE
# ==========================================================

def render_tradingview_table(df):

    if df.empty:
        return

    st.markdown(
        "## 📈 TradingView Quick Access"
    )

    for _, row in df.iterrows():

        c1, c2, c3 = st.columns(
            [2,1,2]
        )

        with c1:

            st.write(
                row["Stock"]
            )

        with c2:

            st.write(
                f"RSI: {row['Current Weekly RSI']}"
            )

        with c3:

            tv_url = (
                f"https://www.tradingview.com/chart/?symbol=NSE:{row['Stock']}"
            )

            st.link_button(
                "Open Chart",
                tv_url
            )


# ==========================================================
# COMPLETE RESULT PIPELINE
# ==========================================================

def process_results_pipeline(
    dataframe,
    search_text=""
):

    if dataframe.empty:

        st.warning(
            "Scanner returned no data."
        )

        return dataframe

    dataframe = format_scanner_results(
        dataframe
    )

    dataframe = add_tradingview_links(
        dataframe
    )

    dataframe = apply_search_filter(
        dataframe,
        search_text
    )

    render_csv_export(
        dataframe
    )

    render_results_table(
        dataframe
    )

    render_tradingview_table(
        dataframe
    )

    return dataframe


# ==========================================================
# FULL SCAN STOCK SELECTION
# ==========================================================

def get_scan_universe(
    nifty500_list,
    full_scan,
    batch_limit
):

    if full_scan:

        return nifty500_list

    return nifty500_list[:batch_limit]


# ==========================================================
# SCAN STATS
# ==========================================================

def render_scan_stats(df):

    if df.empty:
        return

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Matched Stocks",
            len(df)
        )

    with col2:

        st.metric(
            "Average RSI",
            round(
                df["Current Weekly RSI"].mean(),
                2
            )
        )

    with col3:

        st.metric(
            "Average Market Cap",
            round(
                df["Market Cap (Cr)"].mean(),
                2
            )
        )


# ==========================================================
# DUPLICATE TRADE PREVENTION
# ==========================================================

def is_duplicate_trade(
    user_ledger,
    stock_name
):

    active_trades = [

        trade

        for trade in user_ledger

        if trade["Status"] == "ACTIVE"
    ]

    for trade in active_trades:

        if trade["Stock"] == stock_name:

            return True

    return False


# ==========================================================
# WIN RATE ENGINE
# ==========================================================

def calculate_win_rate(
    user_ledger
):

    closed_trades = [

        trade

        for trade in user_ledger

        if trade["Status"] == "CLOSED"
    ]

    if len(closed_trades) == 0:

        return 0.0

    winning_trades = [

        trade

        for trade in closed_trades

        if trade["Total P&L"] > 0
    ]

    win_rate = (

        len(winning_trades)

        / len(closed_trades)

    ) * 100

    return round(
        win_rate,
        2
    )


# ==========================================================
# OPEN POSITIONS
# ==========================================================

def get_open_positions(
    user_ledger
):

    active_positions = [

        trade

        for trade in user_ledger

        if trade["Status"] == "ACTIVE"
    ]

    return len(
        active_positions
    )


# ==========================================================
# CAPITAL UTILIZATION
# ==========================================================

def calculate_capital_utilization(
    user_ledger,
    total_capital
):

    if total_capital <= 0:

        return 0.0

    invested_amount = 0

    for trade in user_ledger:

        if trade["Status"] == "ACTIVE":

            invested_amount += trade[
                "Investment Amt"
            ]

    utilization = (

        invested_amount

        / total_capital

    ) * 100

    return round(
        utilization,
        2
    )


# ==========================================================
# ACTIVE CAPITAL
# ==========================================================

def get_active_capital(
    user_ledger
):

    capital = 0

    for trade in user_ledger:

        if trade["Status"] == "ACTIVE":

            capital += trade[
                "Investment Amt"
            ]

    return round(
        capital,
        2
    )


# ==========================================================
# CLOSED PNL
# ==========================================================

def get_closed_pnl(
    user_ledger
):

    pnl = 0

    for trade in user_ledger:

        if trade["Status"] == "CLOSED":

            pnl += trade[
                "Total P&L"
            ]

    return round(
        pnl,
        2
    )


# ==========================================================
# ACTIVE PNL
# ==========================================================

def get_active_pnl(
    user_ledger
):

    pnl = 0

    for trade in user_ledger:

        if trade["Status"] == "ACTIVE":

            pnl += trade[
                "Total P&L"
            ]

    return round(
        pnl,
        2
    )


# ==========================================================
# DASHBOARD
# ==========================================================

def render_dashboard_metrics(
    user_ledger,
    total_capital
):

    win_rate = calculate_win_rate(
        user_ledger
    )

    open_positions = get_open_positions(
        user_ledger
    )

    capital_utilization = (
        calculate_capital_utilization(
            user_ledger,
            total_capital
        )
    )

    active_pnl = get_active_pnl(
        user_ledger
    )

    booked_pnl = get_closed_pnl(
        user_ledger
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Win Rate %",
            f"{win_rate}%"
        )

    with col2:

        st.metric(
            "Open Positions",
            open_positions
        )

    with col3:

        st.metric(
            "Capital Utilization %",
            f"{capital_utilization}%"
        )

    col4, col5 = st.columns(2)

    with col4:

        st.metric(
            "Active PnL",
            f"₹{active_pnl:,.2f}"
        )

    with col5:

        st.metric(
            "Booked PnL",
            f"₹{booked_pnl:,.2f}"
        )


# ==========================================================
# TRADE ENTRY VALIDATION
# ==========================================================

def validate_trade_entry(
    user_ledger,
    stock_name
):

    duplicate_trade = is_duplicate_trade(
        user_ledger,
        stock_name
    )

    if duplicate_trade:

        st.error(
            f"{stock_name} already exists in ACTIVE trades."
        )

        return False

    return True


# ==========================================================
# SIDEBAR DASHBOARD
# ==========================================================

def render_sidebar_metrics(
    user_ledger,
    total_capital
):

    st.sidebar.markdown(
        "---"
    )

    st.sidebar.subheader(
        "📊 V2 Performance Dashboard"
    )

    st.sidebar.metric(
        "Win Rate %",
        calculate_win_rate(
            user_ledger
        )
    )

    st.sidebar.metric(
        "Open Positions",
        get_open_positions(
            user_ledger
        )
    )

    st.sidebar.metric(
        "Capital Utilization %",
        calculate_capital_utilization(
            user_ledger,
            total_capital
        )
    )


# ==========================================================
# AUTO REFRESH HELPER
# ==========================================================

def auto_refresh_now():

    st.rerun()


# ==========================================================
# END OF MODULE
# ==========================================================
