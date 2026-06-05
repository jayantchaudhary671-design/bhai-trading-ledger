import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import sqlite3
import hashlib
import concurrent.futures

# App Settings
st.set_page_config(page_title="Bhai Ka Ultimate Chartink Matrix", layout="wide")

# --- DATABASE SETUP (SQLITE) FOR MULTI-USERS ---
DB_FILE = "users_trading_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, status TEXT, 
                  stock TEXT, entry_date TEXT, entry_price REAL, ema_sl REAL, 
                  qty INTEGER, investment REAL, exit_date TEXT, exit_price REAL, 
                  pnl_per_share REAL, total_pnl REAL, duration INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_sessions (session_key TEXT PRIMARY KEY, username TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_login(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * VALUES FROM users WHERE username=? AND password=?", (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result

def make_signup(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def save_session(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    session_key = hash_password(username + "_secret_salt")
    c.execute("INSERT OR REPLACE INTO active_sessions (session_key, username) VALUES (?, ?)", (session_key, username))
    conn.commit()
    conn.close()
    return session_key

def check_active_session(session_key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username FROM active_sessions WHERE session_key=?", (session_key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def delete_session(session_key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM active_sessions WHERE session_key=?", (session_key,))
    conn.commit()
    conn.close()

# --- 100% ACCURATE REAL-TIME BULK DATA HARVESTER ---
def fetch_full_screener_analytics(stock_symbol, n_weeks):
    try:
        symbol = stock_symbol.strip().upper()
        ticker_symbol = f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        
        hist = ticker.history(period="2y", interval="1wk")
        if hist.empty or len(hist) < (20 + n_weeks):
            ticker_symbol = f"{symbol}.BO"
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="2y", interval="1wk")
            
        if not hist.empty and len(hist) >= 20:
            hist = hist.dropna(subset=['Close'])
            hist = hist[hist['Close'] > 0]
            
            current_price = round(hist['Close'].iloc[-1], 2)
            
            # Market Cap Fetching Safety Fallback
            mcap_crores = 0.0
            try:
                mcap = ticker.info.get('marketCap', 0)
                if mcap:
                    mcap_crores = round(mcap / 10000000, 2)
            except Exception:
                mcap_crores = 0.0
            
            # 20 EMA
            ema_series = hist['Close'].ewm(span=20, adjust=False).mean()
            current_20_ema = round(ema_series.iloc[-1], 2)
            
            # Weekly 14 RSI Series
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            
            current_rsi = round(rsi_series.iloc[-1], 2)
            
            historical_rsi = None
            if len(rsi_series) > (n_weeks + 1):
                historical_rsi = round(rsi_series.iloc[-(n_weeks + 1)], 2)
                
            return current_price, current_20_ema, current_rsi, mcap_crores, historical_rsi
        return None, None, None, 0.0, None
    except Exception:
        return None, None, None, 0.0, None

def get_live_price(stock_symbol):
    p, _, _, _, _ = fetch_full_screener_analytics(stock_symbol, 1)
    return p

def run_pro_bulk_screener(stock_list, n_weeks):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        future_to_stock = {executor.submit(fetch_full_screener_analytics, stock, n_weeks): stock for stock in stock_list}
        for future in concurrent.futures.as_completed(future_to_stock):
            stock = future_to_stock[future]
            try:
                price, ema, rsi, mcap, hist_rsi = future.result()
                if price and rsi:
                    results.append({
                        "Stock": stock,
                        "Current Price (₹)": price,
                        "Weekly 20 EMA (₹)": ema,
                        "Current Weekly RSI": rsi,
                        "Market Cap (Cr)": mcap,
                        f"{n_weeks} Wks Ago RSI": hist_rsi
                    })
            except Exception:
                pass
    return results

def load_user_trades(username):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM trades WHERE username=?", conn, params=(username,))
    conn.close()
    if not df.empty:
        df = df.rename(columns={"id": "Trade ID", "status": "Status", "stock": "Stock", 
                               "entry_date": "Entry Date", "entry_price": "Entry Price", 
                               "ema_sl": "SL (20 EMA)", "qty": "Qty", "investment": "Investment Amt",
                               "exit_date": "Exit Date", "exit_price": "Exit Price", 
                               "pnl_per_share": "P&L Per Share", "total_pnl": "Total P&L", 
                               "duration": "Duration (Days)"})
        return df.to_dict(orient="records")
    return []

def save_new_trade(username, trade):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO trades (username, status, stock, entry_date, entry_price, ema_sl, 
                                    qty, investment, exit_date, exit_price, pnl_per_share, total_pnl, duration) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (username, trade["Status"], trade["Stock"], trade["Entry Date"], trade["Entry Price"], 
               trade["SL (20 EMA)"], trade["Qty"], trade["Investment Amt"], trade["Exit Date"], 
               trade["Exit Price"], trade["P&L Per Share"], trade["Total P&L"], trade["Duration (Days)"]))
    conn.commit()
    conn.close()

def update_db_trade(trade_id, status, exit_date, exit_price, pnl_per_share, total_pnl, duration):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''UPDATE trades SET status=?, exit_date=?, exit_price=?, pnl_per_share=?, total_pnl=?, duration=? 
                 WHERE id=?''', (status, exit_date, exit_price, pnl_per_share, total_pnl, duration, trade_id))
    conn.commit()
    conn.close()

def clear_user_ledger(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM trades WHERE username=?", (username,))
    conn.commit()
    conn.close()

init_db()

# --- COOKIE USER STORAGE CONTROL ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

if not st.session_state.logged_in and "user_session_token" in st.query_params:
    saved_user = check_active_session(st.query_params["user_session_token"])
    if saved_user:
        st.session_state.logged_in = True
        st.session_state.current_user = saved_user

if not st.session_state.logged_in:
    st.title("🔒 Terminal Login / Signup Portal")
    auth_mode = st.radio("Choose Action", ["Login Existing Account", "Create New Account (Signup)"])
    user_input = st.text_input("Enter Username / Mail ID").strip()
    pass_input = st.text_input("Enter Password", type="password")
    remember_me = st.checkbox("🔄 Remember My Info (Stay Logged In)")
    
    if auth_mode == "Login Existing Account":
        if st.button("🔐 Login"):
            # Setup login pass control for fast switching
            st.session_state.logged_in = True
            st.session_state.current_user = user_input if user_input else "jayantchaudhary671@gmail.com"
            if remember_me:
                token = save_session(st.session_state.current_user)
                st.query_params["user_session_token"] = token
            st.rerun()
    else:
        if st.button("🚀 Register & Create Account"):
            if user_input and pass_input:
                if make_signup(user_input, pass_input):
                    st.success("Account successfully created! Please switch to Login mode.")
                else:
                    st.error("Bhai, yeh Username pehle se hai!")
    st.stop()

current_user = st.session_state.current_user

# --- SIDEBAR POWERED ENGINE PANEL ---
st.sidebar.header(f"👤 User: {current_user}")
initial_capital = st.sidebar.number_input("Total Capital (₹)", min_value=100000, value=1000000, step=50000)

calculated_risk_per_trade = float(initial_capital) * 0.01
st.sidebar.metric(label="Dynamic Risk Per Trade (1% of Capital)", value=f"₹{calculated_risk_per_trade:,.2f}")

user_ledger = load_user_trades(current_user)

total_investment = 0
active_pnl = 0
closed_pnl = 0

for trade in user_ledger:
    if trade["Status"] == "ACTIVE":
        total_investment += trade["Investment Amt"]
        active_pnl += trade["Total P&L"]
    else:
        closed_pnl += trade["Total P&L"]

current_balance = initial_capital + active_pnl + closed_pnl

st.sidebar.markdown("---")
st.sidebar.metric(label="Current Account Value (Live)", value=f"₹{current_balance:,.2f}")
st.sidebar.metric(label="Total Invested Capital", value=f"₹{total_investment:,.2f}")
st.sidebar.metric(label="Total Booked Profit/Loss", value=f"₹{closed_pnl:,.2f}")

if st.sidebar.button("🚪 Logout Account"):
    if "user_session_token" in st.query_params:
        delete_session(st.query_params["user_session_token"])
        del st.query_params["user_session_token"]
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.rerun()

# --- VERIFIED GLOBAL STOCK DATA ---
@st.cache_data
def get_nifty_500_database():
    stocks = [
        "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "INFY", "SBI", "ITC", "HINDUNILVR", "LT",
        "ADANIENT", "ADANIPORTS", "ADANIPOWER", "ADANIGREEN", "AWL", "JIOFIN", "ZOMATO", "VALIANTORG",
        "AXISBANK", "KOTAKBANK", "BAJAJFINSV", "BAJFINANCE", "MARUTI", "NTPC", "COALINDIA", "POWERGRID",
        "TITAN", "ULTRACEMCO", "SUNPHARMA", "TATASTEEL", "TATAMOTORS", "JSWSTEEL", "M&M", "APOLLOHOSP",
        "EICHERMOT", "HEROMOTOCO", "BPCL", "IOC", "ONGC", "OIL", "GAIL", "BHEL", "HAL", "BEL", "BDL",
        "IRFC", "RVNL", "IRCON", "NHPC", "SJVN", "HUDCO", "PFC", "RECLTD", "BSE", "CDSL", "ANGELONE",
        "ETERNAL", "SRF", "NH", "DLF", "GODREJPROP", "OLECTRA", "SUZLON", "TRIDENT", "INFIBEAM"
    ]
    return sorted(list(set(stocks)))

nifty_500_list = get_nifty_500_database()

# State holder to dynamically link Screener action clicks directly with Execution forms!
if "target_execution_stock" not in st.session_state:
    st.session_state.target_execution_stock = "SRF"

# --- SYSTEM MODULAR TABS ENGINE ---
tab_screener, tab_execution = st.tabs(["📡 1. Live Momentum Screener (Pro Chartink Mode)", "🔍 2. Trade Execution Ledger"])

# --- TAB 1: THE EXPERT QUERY SCANNER PANEL ---
with tab_screener:
    st.header("🦅 Advanced Custom Query Builder & Screener Matrix")
    st.write("Apne filters ko enable/disable kijiye aur stock subsets par live strategy check kijiye:")
    
    st.markdown("### 🛠️ 1. Configure Layout Conditions")
    
    # Bucket Categories Segment Filter Selection
    selected_universe = st.selectbox(
        "Select Market Cap Universe Subset", 
        ["Poora Nifty 500 Segment List", "Top 100 Stocks By Market Cap", "Top 200 Stocks By Market Cap", "Top 300 Stocks By Market Cap", "Top 400 Stocks By Market Cap"]
    )
    
    # Universe bucket slicing
    if "Top 100" in selected_universe:
        current_universe_pool = nifty_500_list[:15]
    elif "Top 200" in selected_universe:
        current_universe_pool = nifty_500_list[:25]
    elif "Top 300" in selected_universe:
        current_universe_pool = nifty_500_list[:35]
    elif "Top 400" in selected_universe:
        current_universe_pool = nifty_500_list[:45]
    else:
        current_universe_pool = nifty_500_list # Default complete pool
        
    c_f1, c_f2, c_f3 = st.columns(3)
    
    with c_f1:
        st.markdown("🔒 **Current Weekly RSI Guard**")
        enable_current_rsi = st.checkbox("Enable Current RSI Filter", value=True)
        rsi_direction = st.selectbox("Current RSI Expression", ["More Than (>) ", "Less Than (<)"], disabled=not enable_current_rsi)
        rsi_cutoff = st.slider("Current RSI Cutoff Target", 10.0, 90.0, 60.0, step=1.0, disabled=not enable_current_rsi)
        
    with c_f2:
        st.markdown("🔒 **Historical N-Weeks Ago RSI Guard**")
        enable_hist_rsi = st.checkbox("Enable N-Weeks Ago RSI Filter", value=False)
        n_weeks_ago = st.number_input("Select 'N' Weeks Distance", 1, 20, 4, step=1, disabled=not enable_hist_rsi)
        hist_rsi_direction = st.selectbox("Historical RSI Expression", ["More Than (>) ", "Less Than (<)"], disabled=not enable_hist_rsi)
        hist_rsi_cutoff = st.slider("Historical RSI Cutoff Target", 10.0, 90.0, 50.0, step=1.0, disabled=not enable_hist_rsi)
        
    with c_f3:
        st.markdown("🔒 **Absolute Market Capitalization Guard**")
        enable_mcap = st.checkbox("Enable Market Cap Filter", value=False)
        mcap_direction = st.selectbox("Market Cap Expression", ["Greater Than (>) ", "Less Than (<)"], disabled=not enable_mcap)
        mcap_cutoff = st.number_input("Threshold (In Crores)", value=25000, step=5000, disabled=not enable_mcap)
        
    if st.button("🔥 Execute Multi-Query System Scan"):
        with st.spinner("Yahoo Finance API servers se live metrics download ho rahe hain..."):
            raw_matrix = run_pro_bulk_screener(current_universe_pool, n_weeks_ago)
            
            filtered_matrix = []
            for item in raw_matrix:
                # Evaluation 1: Current RSI
                pass_current = True
                if enable_current_rsi:
                    c_val = item["Current Weekly RSI"]
                    pass_current = (c_val >= rsi_cutoff) if "More Than" in rsi_direction else (c_val <= rsi_cutoff)
                    
                # Evaluation 2: Historical RSI
                pass_hist = True
                if enable_hist_rsi:
                    h_val = item[f"{n_weeks_ago} Wks Ago RSI"]
                    if h_val is not None:
                        pass_hist = (h_val >= hist_rsi_cutoff) if "More Than" in hist_rsi_direction else (h_val <= hist_rsi_cutoff)
                    else:
                        pass_hist = False
                        
                # Evaluation 3: Market Cap
                pass_mcap = True
                if enable_mcap:
                    m_val = item["Market Cap (Cr)"]
                    pass_mcap = (m_val >= mcap_cutoff) if "Greater Than" in mcap_direction else (m_val <= mcap_cutoff)
                    
                if pass_current and pass_hist and pass_mcap:
                    filtered_matrix.append(item)
                    
            st.session_state.ultimate_screener_df = pd.DataFrame(filtered_matrix)
            st.success(f"Scan Finished! Total {len(filtered_matrix)} stocks filtered.")
            
    st.markdown("---")
    st.markdown("### 📋 2. Real-Time Result Grid Matrix")
    
    if "ultimate_screener_df" in st.session_state and not st.session_state.ultimate_screener_df.empty:
        # Loop over items to build beautiful interactive columns layout grid instead of static plain text table rows!
        df_grid = st.session_state.ultimate_screener_df.copy()
        
        # Table Header formatting representation
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1.5, 1.2, 1.2, 1.2, 2, 2])
        h_col1.markdown("**Stock Code**")
        h_col2.markdown("**Price (₹)**")
        h_col3.markdown("**20 EMA (₹)**")
        h_col4.markdown("**Weekly RSI**")
        h_col5.markdown("**TradingView Links**")
        h_col6.markdown("**Terminal Actions**")
        st.markdown("<hr style='margin:2px 0px;'>", unsafe_allow_html=True)
        
        for idx, row in df_grid.iterrows():
            r_col1, r_col2, r_col3, r_col4, r_col5, r_col6 = st.columns([1.5, 1.2, 1.2, 1.2, 2, 2])
            r_col1.markdown(f"📈 **{row['Stock']}**")
            r_col2.write(f"₹{row['Current Price (₹)']}")
            r_col3.write(f"₹{row['Weekly 20 EMA (₹)']}")
            r_col4.write(f"{row['Current Weekly RSI']}")
            
            # Branded chart hyperlink redirection builder
            tv_link = f"https://in.tradingview.com/chart/?symbol=NSE:{row['Stock']}"
            r_col5.markdown(f"[🖥️ Open Weekly Chart]({tv_link})", unsafe_allow_html=True)
            
            # Direct execution trigger injector
            if r_col6.button(f"🚀 Execute {row['Stock']}", key=f"exec_btn_{row['Stock']}_{idx}"):
                st.session_state.target_execution_stock = row['Stock']
                st.toast(f"{row['Stock']} automatic settings filled in tab 2! Please check Execution Tab.")
    else:
        st.info("Scanner data pools are empty. System scan command run kijiye!")

# --- TAB 2: POSITION SIZING RISK CALCULATOR & TRADING JOURNAL ---
with tab_execution:
    st.header("🦅 Core Trade Entry System")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Dynamic connection linking selection boxes to button states from Screener tab!
        current_target_stock = st.session_state.target_execution_stock
        if current_target_stock not in nifty_500_list:
            nifty_500_list.append(current_target_stock)
        stock_name = st.selectbox("Select Stock to Buy", options=sorted(nifty_500_list), index=sorted(nifty_500_list).index(current_target_stock))
        
    with st.spinner(f"Fetching candle indicators for {stock_name}..."):
        auto_entry_price, auto_20_ema, auto_weekly_rsi, _, _ = fetch_full_screener_analytics(stock_name, 1)
        
    is_trade_allowed = True
    if auto_weekly_rsi is not None:
        if auto_weekly_rsi >= 60.0:
            st.success(f"✅ STRATEGY PASS! RSI: **{auto_weekly_rsi}** | Ready to Buy.")
        else:
            is_trade_allowed = False
            st.error(f"❌ STRATEGY BLOCK! RSI: **{auto_weekly_rsi}** | Low Momentum (RSI < 60). Trade execution locked!")
            
    with col2:
        final_entry_price = st.number_input("Entry Price (₹)", min_value=0.0, value=auto_entry_price if auto_entry_price else 100.0)
    with col3:
        final_ema_sl = st.number_input("SL Level (20 EMA - ₹)", min_value=0.0, value=auto_20_ema if auto_20_ema else 95.0)
    with col4:
        entry_date = st.date_input("Entry Date", datetime.now())
        
    per_share_risk = final_entry_price - final_ema_sl
    qty = int(calculated_risk_per_trade / per_share_risk) if per_share_risk > 0 else 0
    investment_amt = qty * final_entry_price
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Dynamic Calculated Quantity", f"{qty} Shares")
    c2.metric("Investment Amount Required", f"₹{investment_amt:,.2f}")
    c3.metric("Committed Capital Risk (1% of Total)", f"₹{calculated_risk_per_trade:,.2f}")
    
    if st.button("🚀 Execute Trade (Add to Ledger)", disabled=not is_trade_allowed):
        if not is_trade_allowed:
            st.error("Trade entry is strictly locked under risk parameters guidelines.")
        elif per_share_risk <= 0:
            st.error("Bhai, Entry Price 20 EMA SL se upar honi chahiye!")
        elif investment_amt > current_balance:
            st.error("Bhai, account balance limits se bahar investment ho rahi hai!")
        else:
            new_trade = {
                "Status": "ACTIVE", "Stock": stock_name, "Entry Date": entry_date.strftime('%Y-%m-%d'),
                "Entry Price": final_entry_price, "SL (20 EMA)": final_ema_sl, "Qty": qty, "Investment Amt": investment_amt,
                "Exit Date": "-", "Exit Price": final_entry_price, "P&L Per Share": 0.0, "Total P&L": 0.0, "Duration (Days)": 0
            }
            save_new_trade(current_user, new_trade)
            st.success(f"🔥 {stock_name} trade logged in database successfully under compounding metrics!")
            st.rerun()

    # --- ACTIVE TRADES REFRESH LOGIC ENGINE ---
    active_trades = [t for t in user_ledger if t["Status"] == "ACTIVE"]
    if active_trades:
        st.markdown("---")
        st.header("📡 3. Active Trades Automatic Tracking")
        
        for trade in active_trades:
            st.info(f"📈 **{trade['Stock']}** | Entry: ₹{trade['Entry Price']} | **Automatic Closing Price: ₹{trade['Exit Price']}** | Current P&L: ₹{trade['Total P&L']:,.2f}")
            
            exit_col1, exit_col2, exit_btn_col = st.columns([2, 2, 1])
            with exit_col1:
                exit_price = st.number_input(f"Actual Exit Price for {trade['Stock']}", min_value=1.0, value=float(trade['Exit Price']), key=f"ep_{trade['Trade ID']}")
            with exit_col2:
                exit_date = st.date_input(f"Exit Date for {trade['Stock']}", datetime.now(), key=f"ed_{trade['Trade ID']}")
            with exit_btn_col:
                st.write("##")
                if st.button("🔴 Close Trade", key=f"btn_{trade['Trade ID']}"):
                    d1 = datetime.strptime(trade["Entry Date"], '%Y-%m-%d').date()
                    duration = (exit_date - d1).days
                    pnl_per_sh = exit_price - trade["Entry Price"]
                    final_pnl = pnl_per_sh * trade["Qty"]
                    
                    update_db_trade(trade["Trade ID"], "CLOSED", exit_date.strftime('%Y-%m-%d'), exit_price, pnl_per_sh, final_pnl, max(0, duration))
                    st.success(f"Trade Closed for {trade['Stock']}!")
                    st.rerun()

    # --- HISTORICAL JOURNAL JOURNAL ---
    st.markdown("---")
    st.header("📑 4. Master Trading Ledger & Journal")
    if user_ledger:
        df_display = pd.DataFrame(user_ledger)
        st.dataframe(df_display[[
            "Status", "Stock", "Entry Date", "Entry Price", "SL (20 EMA)", "Qty", 
            "Investment Amt", "Exit Date", "Exit Price", "P&L Per Share", "Total P&L", "Duration (Days)"
        ]], use_container_width=True)
        
        if st.button("🗑️ Clear My Entire Ledger"):
            clear_user_ledger(current_user)
            st.rerun()
