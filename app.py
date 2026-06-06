import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import sqlite3
import hashlib
import concurrent.futures

# App Config
st.set_page_config(page_title="Bhai Ka Ultimate Terminal", layout="wide")

# --- DATABASE SETUP ---
DB_FILE = "users_trading_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, status TEXT, stock TEXT, entry_date TEXT, entry_price REAL, ema_sl REAL, qty INTEGER, investment REAL, exit_date TEXT, exit_price REAL, pnl_per_share REAL, total_pnl REAL, duration INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_sessions (session_key TEXT PRIMARY KEY, username TEXT)''')
    conn.commit()
    conn.close()

def hash_pw(pwd): return hashlib.sha256(str.encode(pwd)).hexdigest()

def check_login(user, pwd):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, hash_pw(pwd)))
    res = c.fetchone()
    conn.close()
    return res

def make_signup(user, pwd):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, hash_pw(pwd)))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

init_db()

# --- ANALYTICS ENGINE ---
def fetch_screener_data(stock, n_weeks):
    try:
        ticker = yf.Ticker(f"{stock}.NS")
        hist = ticker.history(period="2y", interval="1wk")
        if hist.empty:
            ticker = yf.Ticker(f"{stock}.BO")
            hist = ticker.history(period="2y", interval="1wk")
        if len(hist) < 20: return None, None, None, 0, None
        
        hist = hist.dropna(subset=['Close'])
        price = round(hist['Close'].iloc[-1], 2)
        mcap = round(ticker.info.get('marketCap', 0) / 10000000, 2)
        ema = round(hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1], 2)
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = round((100 - (100 / (1 + (gain / loss)))).iloc[-1], 2)
        hist_rsi = round((100 - (100 / (1 + (gain.iloc[-n_weeks] / loss.iloc[-n_weeks])))), 2)
        return price, ema, rsi, mcap, hist_rsi
    except: return None, None, None, 0, None

def run_screener(stock_list, n_weeks):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_stock = {executor.submit(fetch_screener_data, stock, n_weeks): stock for stock in stock_list}
        for future in concurrent.futures.as_completed(future_to_stock):
            stock = future_to_stock[future]
            price, ema, rsi, mcap, hist_rsi = future.result()
            if price:
                results.append({"Stock": stock, "Price (₹)": price, "20 EMA": ema, "Current RSI": rsi, "Market Cap (Cr)": mcap, f"{n_weeks} Wks Ago RSI": hist_rsi})
    return results

# Database actions for trades
def load_user_trades(user):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM trades WHERE username=?", conn, params=(user,))
    conn.close()
    if not df.empty:
        df = df.rename(columns={"id": "Trade ID", "status": "Status", "stock": "Stock", "entry_date": "Entry Date", "entry_price": "Entry Price", "ema_sl": "SL (20 EMA)", "qty": "Qty", "investment": "Investment Amt", "exit_date": "Exit Date", "exit_price": "Exit Price", "pnl_per_share": "P&L Per Share", "total_pnl": "Total P&L", "duration": "Duration (Days)"})
        return df.to_dict(orient="records")
    return []

def save_new_trade(user, trade):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO trades (username, status, stock, entry_date, entry_price, ema_sl, qty, investment, exit_date, exit_price, pnl_per_share, total_pnl, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (user, trade["Status"], trade["Stock"], trade["Entry Date"], trade["Entry Price"], trade["SL (20 EMA)"], trade["Qty"], trade["Investment Amt"], trade["Exit Date"], trade["Exit Price"], trade["P&L Per Share"], trade["Total P&L"], trade["Duration (Days)"]))
    conn.commit()
    conn.close()

def update_db_trade(trade_id, status, exit_date, exit_price, pnl_per_share, total_pnl, duration):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''UPDATE trades SET status=?, exit_date=?, exit_price=?, pnl_per_share=?, total_pnl=?, duration=? WHERE id=?''', (status, exit_date, exit_price, pnl_per_share, total_pnl, duration, trade_id))
    conn.commit()
    conn.close()

def clear_user_ledger(user):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM trades WHERE username=?", (user,))
    conn.commit()
    conn.close()

# --- LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

if not st.session_state.logged_in:
    st.title("🔒 Terminal Login")
    auth_mode = st.radio("Action", ["Login", "Signup"])
    user_input = st.text_input("Username").strip()
    pass_input = st.text_input("Password", type="password")
    
    if auth_mode == "Login":
        if st.button("Login"):
            if check_login(user_input, pass_input):
                st.session_state.logged_in = True
                st.session_state.current_user = user_input
                st.rerun()
            else: st.error("Galat Username/Password!")
    else:
        if st.button("Signup"):
            if make_signup(user_input, pass_input): st.success("Created! Please Login.")
            else: st.error("Username already exists!")
    st.stop()

current_user = st.session_state.current_user

# --- SIDEBAR METRICS ---
st.sidebar.header(f"👤 User: {current_user}")
initial_capital = st.sidebar.number_input("Total Capital (₹)", min_value=100000, value=1000000, step=50000)
risk_per_trade = float(initial_capital) * 0.01

user_ledger = load_user_trades(current_user)
total_investment = sum(t["Investment Amt"] for t in user_ledger if t["Status"] == "ACTIVE")
active_pnl = sum(t["Total P&L"] for t in user_ledger if t["Status"] == "ACTIVE")
closed_pnl = sum(t["Total P&L"] for t in user_ledger if t["Status"] == "CLOSED")
current_balance = initial_capital + active_pnl + closed_pnl

st.sidebar.metric("Dynamic Risk Per Trade (1%)", f"₹{risk_per_trade:,.2f}")
st.sidebar.markdown("---")
st.sidebar.metric("Current Account Value (Live)", f"₹{current_balance:,.2f}")
st.sidebar.metric("Total Invested Capital", f"₹{total_investment:,.2f}")
st.sidebar.metric("Total Booked Profit/Loss", f"₹{closed_pnl:,.2f}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.rerun()

# 🛠️ NIFTY 500 FULL LIST (SORTED ROUGHLY BY MARKET CAP DESCENDING)
raw_nifty_500 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "INFY", "SBIN", "HINDUNILVR", "ITC", "LT",
    "BAJFINANCE", "HCLTECH", "KOTAKBANK", "ADANIENT", "AXISBANK", "NTPC", "TATAMOTORS", "SUNPHARMA", "ONGC", "M&M",
    "TATASTEEL", "POWERGRID", "COALINDIA", "BAJAJFINSV", "ASIANPAINT", "ADANIPORTS", "MARUTI", "ULTRACEMCO", "TITAN", "WIPRO",
    "NESTLEIND", "JSWSTEEL", "GRASIM", "TECHM", "HAL", "ZOMATO", "DLF", "IOC", "LTIM", "SBILIFE",
    "HDFCLIFE", "BAJAJ-AUTO", "BHEL", "INDUSINDBK", "GODREJCP", "EICHERMOT", "DIVISLAB", "DRREDDY", "BPCL", "BEL",
    "TRENT", "CHOLAFIN", "CIPLA", "TORNTPHARM", "PFC", "RECLTD", "GAIL", "AMBUJACEM", "SRF", "SHREECEM",
    "TATACHEM", "TATACOMM", "TATACONSUM", "TATAELXSI", "TATAINVEST", "TATAPOWER", "TATATECH", "TVSMOTOR", "UBL", "UCOBANK",
    "UNIONBANK", "MCDOWELL-N", "VBL", "VEDL", "VOLTAS", "YESBANK", "ZEEL", "ZENSARTECH", "ZYDUSLIFE", "ABB", "ACC",
    "AUBANK", "AARTIIND", "ABBOTINDIA", "ADANIGREEN", "ADANIPOWER", "ADANITOTAL", "AWL", "ABCAPITAL", "ABFRL",
    "APOLLOHOSP", "APOLLOTYRE", "ASTRAL", "ATUL", "AUROPHARMA", "DMART", "BEML", "BSE", "BALKRISIND", "BALRAMCHIN",
    "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BATAINDIA", "BDL", "BHARATFORG", "BIOCON", "BSOFT", "BRIGADE", "BRITANNIA",
    "CGPOWER", "CANBK", "CASTROLIND", "CHAMBLFERT", "CLEAN", "COCHINSHIP", "COFORGE", "COLPAL", "CROMPTON", "CUMMINSIND",
    "CYIENT", "DABUR", "DALBHARAT", "DEEPAKNTR", "DELHIVERY", "DIXON", "LALPATHLAB", "EASEMYTRIP", "ESCORTS", "EXIDEIND",
    "FEDERALBNK", "FACT", "FORTIS", "GMMPFAUDLR", "GMRINFRA", "GLAND", "GLENMARK", "GODFRYPHLP", "GODREJIND", "GODREJPROP",
    "GRANULES", "GUJGASLTD", "GNFC", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HUDCO", "ICICIGI", "ICICIPRULI", "IDFCFIRSTB",
    "IDFC", "IRCTC", "IRFC", "INDIACEM", "INDIAMART", "INDIANB", "IEX", "INDIGO", "INDUSTOWER", "IPCALAB",
    "JKCEMENT", "JSWENERGY", "JINDALSTEL", "JUBLFOOD", "KALYANKJIL", "KANSAINER", "KEI", "KPITTECH", "LICI", "LAURUSLABS",
    "LUPIN", "MRF", "M&MFIN", "MANAPPURAM", "MARICO", "MAXHEALTH", "MAZDOCK", "METROPOLIS", "MSUMI", "MCX",
    "MUTHOOTFIN", "NATCOPHARM", "NBCC", "NCC", "NHPC", "NLCINDIA", "NMDC", "NOCIL", "NH", "NATIONALUM",
    "NAVINFLUOR", "OBEROIRLTY", "OIL", "OLECTRA", "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PHOENIXLTD", "PIDILITIND",
    "PIIND", "POLYCAB", "POONAWALLA", "PRESTIGE", "RBLBANK", "RVNL", "RAILTEL", "RAMCOCEM", "RAYMOND", "RELAXO",
    "SAIL", "SCHAEFFLER", "SONACOMS", "STARHEALTH", "SYNGENE", "TV18BRDCST", "THERMAX", "UPL", "ETERNAL",
    "360ONE", "3MINDIA", "AIAENG", "APLAPOLLO", "AAVAS", "AEGISCHEM", "AETHER", "AFFLE", "AJANTPHARM", "APLLTD",
    "ALKEM", "ALKYLAMINE", "ALLCARGO", "ALOKINDS", "ARE&M", "ANGELONE", "ANURAS", "APARINDS", "APTUS", "ACI",
    "ASTERDM", "AVANTIFEED", "BLS", "BAYERCROP", "BERGEPAINT", "BHALQ", "BORORENEW", "BOSCHLTD", "MAPMYINDIA", "CCL",
    "CESC", "CIEINDIA", "CRISIL", "CSBBANK", "CAMPUS", "CANFINHOME", "CAPLIPOINT", "CGCL", "CARBORUNV", "CEATLTD",
    "CENTRALBK", "CENTURYPLY", "CENTURYTEX", "CERA", "CHALET", "CREDITACC", "DCAL", "DCBBANK", "DATAPATTNS", "DEEPAKFERT",
    "DEVYANI", "DONEAR", "EIDPARRY", "EIHOTEL", "EPL", "ELECON", "ELGIEQUIP", "EMAMILTD", "ENDOCO", "ENGINERSIN",
    "ERIS", "FINCABLES", "FINPIPE", "FLUOROCHEM", "GRINFRA", "GATEWAY", "GENUSPOWER", "GOCOLORS", "GRAPHITE", "GESHIP",
    "GREENPANEL", "GRINDWELL", "GUJALKALI", "GMDCLTD", "GSFC", "GSPL", "HEG", "HFCL", "HLEGLAS", "HIKAL",
    "HINDZINC", "HOMEFIRST", "HONAUT", "IRIS", "ITI", "INFIBEAM", "INGERRAND", "INOXWIND", "INTELLECT", "INDHOTEL",
    "JBCHEPHARM", "JKLAC", "JKPAPER", "JMFINANCIL", "JSWINFRA", "JAIBALAJI", "JAMNAAUTO", "J&KBANK", "JINDALSAW", "JINDALPOLY",
    "JAL", "JUSTDIAL", "JYOTHYLAB", "KIMS", "KNRCON", "KRBL", "KSB", "KAJARIACER", "KALPATOGRPH", "KARURVYSYA",
    "KEC", "KENNAMET", "KFINTECH", "KIRLOSENG", "KIRLOSIND", "KREBSBIO", "KRISHANA", "LTFOODS", "LTSHRE", "LICHSGFIN",
    "LAXMIMACH", "LEMONTREE", "LINDEINDIA", "LUXIND", "MMTC", "MOIL", "MTARTECH", "MHRIL", "MAHLOG", "MAHSEAMLES",
    "MAHITH", "MANGCHEFER", "MRPL", "MASTEK", "MAXESTATES", "MEDANTA", "MEDIASSIST", "MEDPLUS", "MINDACORP", "MOFSL",
    "MOLDTECH", "MOTHERSUMI", "MOTOROD", "MPHASIS", "NESCO", "NFL", "NESF", "NETWEB", "NETWORK18", "NUCLEUS",
    "NUVAMA", "NUVOCO", "OMAXE", "OPTIMUS", "ORCHIDPHAR", "ORIENTELEC", "PNCINFRA", "PVRINOX", "PAGEIND", "PANAMAPET",
    "PARADEEP", "PARAS", "PATELENG", "PEL", "POLYMED", "POLYPLEX", "POWERMECH", "PRAJIND", "PRICOLLTD", "PRINCEPIPE",
    "PRSMJOHNSN", "PRIVISCL", "PRUDENT", "QUESS", "RHIM", "RITES", "RADICO", "RAIN", "RAJESHEXPO", "RALLIS",
    "RAMASTEEL", "RAMCOIND", "RAMCOSYS", "RATNAMANI", "RTNINDIA", "REDINGTON", "RELINFRA", "RELPOWER", "RENUKA", "RBA",
    "RISHABH", "ROLEXRINGS", "ROSSARI", "ROUTE", "SBICARD", "SKFINDIA", "SANSERA", "SAPPHIRE", "SAREGAMA", "SARDAEN",
    "SCHNEIDER", "SEQUENT", "SHAKTIPUMP", "SHAILY", "SHALBY", "SHANKARA", "SHARDAMOTR", "SHARDACROP", "SHAREINDIA", "SHOPERSTOP",
    "SHRIRAMFIN", "SIEMENS", "SIGNATURE", "SILVERQ", "SOBHA", "SOLARINDS", "SONATSOFTW", "SOUTHBANK", "SPANDANA", "SPARC",
    "SRHHL", "STEELCAS", "STERTOOLS", "STLTECH", "SUMICHEM", "SPHARM", "SUNTV", "SUNDARMFIN", "SUNDRMFAST", "SUNTECK",
    "SUPRAJIT", "SUPREMEIND", "SWANENERGY", "SYRMA", "TEGA", "TVSSCS", "TVSHLTD", "TASTYBITE", "TEJASNET", "TEXRAIL",
    "THGROUP", "THYROCARE", "TIINDIA", "TIMKEN", "TRITURBINE", "TRIVENI", "TRU", "UNOMINDA", "UTIAMC", "UJJIVANSFB",
    "UNIPARTS", "UNITEDTEA", "USHAMART", "VGUARD", "V-MART", "VIPIND", "VAIBHAVGBL", "VAKRANGEE", "VALIANTORG", "VRLLOG",
    "VESUVIUS", "VESTIND", "WELCORP", "WELSPUNLIV", "WESTLIFE", "WHIRLPOOL", "WOCKPHARM", "WONDERLA", "XCHANGING", "ZYDUSWELL"
]

nifty_500_list = list(dict.fromkeys(raw_nifty_500))

# --- UI TABS ---
st.title("🦅 Ultimate Strategy Terminal")
tab_scan, tab_exec = st.tabs(["📡 Screener Matrix", "🔍 Trade Execution & Ledger"])

if "target_stock" not in st.session_state: st.session_state.target_stock = "SRF"

with tab_scan:
    st.header("Custom Multi-Filter Scanner")
    bucket = st.selectbox("Select Market Cap Universe", ["Top 100", "Top 200", "Top 300", "Top 400", "All 500"])
    
    slice_idx = 100 if "100" in bucket else (200 if "200" in bucket else (300 if "300" in bucket else (400 if "400" in bucket else len(nifty_500_list))))
    scan_pool = nifty_500_list[:slice_idx]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Current RSI Filters**")
        en_gt = st.checkbox("Enable Min RSI (>)")
        val_gt = st.slider("Min RSI Value", 10.0, 90.0, 60.0, disabled=not en_gt)
        en_lt = st.checkbox("Enable Max RSI (<)")
        val_lt = st.slider("Max RSI Value", 10.0, 90.0, 75.0, disabled=not en_lt)
        
    with c2:
        st.markdown("**Historical RSI Filters**")
        en_h = st.checkbox("Enable Hist RSI")
        n_weeks = st.number_input("N Weeks Ago", 1, 20, 4, disabled=not en_h)
        h_dir = st.selectbox("Condition", ["More Than (>)", "Less Than (<)"], disabled=not en_h)
        h_val = st.slider("Hist RSI Cutoff", 10.0, 90.0, 50.0, disabled=not en_h)
        
    with c3:
        st.markdown("**Market Cap Filters**")
        en_mcap = st.checkbox("Enable Market Cap Filter")
        mcap_dir = st.selectbox("MCap Condition", ["More Than (>)", "Less Than (<)"], disabled=not en_mcap)
        mcap_val = st.number_input("Threshold (Cr)", value=20000, disabled=not en_mcap)

    if st.button("🔥 Run Strategy Scan"):
        with st.spinner("Scanning real-time data for " + str(slice_idx) + " stocks..."):
            raw_data = run_screener(scan_pool, n_weeks)
            df = pd.DataFrame(raw_data)
            
            if not df.empty:
                if en_gt: df = df[df["Current RSI"] > val_gt]
                if en_lt: df = df[df["Current RSI"] < val_lt]
                if en_mcap:
                    if "More Than" in mcap_dir: df = df[df["Market Cap (Cr)"] > mcap_val]
                    else: df = df[df["Market Cap (Cr)"] < mcap_val]
                if en_h:
                    if "More Than" in h_dir: df = df[df[f"{n_weeks} Wks Ago RSI"] > h_val]
                    else: df = df[df[f"{n_weeks} Wks Ago RSI"] < h_val]
                
                st.success(f"Scan Complete! Found {len(df)} matching stocks.")
                
                st.markdown("---")
                h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1, 1, 1.5, 1.5, 1.5])
                h1.write("**Stock**"); h2.write("**Price**"); h3.write("**RSI**"); h4.write("**MCap(Cr)**"); h5.write("**Chart**"); h6.write("**Action**")
                st.markdown("<hr style='margin:0px;'>", unsafe_allow_html=True)
                
                for idx, row in df.iterrows():
                    r1, r2, r3, r4, r5, r6 = st.columns([1.5, 1, 1, 1.5, 1.5, 1.5])
                    r1.markdown(f"**{row['Stock']}**")
                    r2.write(f"₹{row['Price (₹)']}")
                    r3.write(f"{row['Current RSI']}")
                    r4.write(f"{row['Market Cap (Cr)']}")
                    r5.markdown(f"[TradingView](https://in.tradingview.com/chart/?symbol=NSE:{row['Stock']})")
                    if r6.button("🚀 Execute", key=f"btn_{row['Stock']}"):
                        st.session_state.target_stock = row['Stock']
                        st.toast(f"{row['Stock']} selected! Go to Execution Tab.")
            else:
                st.warning("No data found. Check your filters.")

with tab_exec:
    st.header("🦅 Core Trade Entry System")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.session_state.target_stock not in nifty_500_list: nifty_500_list.append(st.session_state.target_stock)
        sel_stock = st.selectbox("Select Stock to Buy", sorted(nifty_500_list), index=sorted(nifty_500_list).index(st.session_state.target_stock))
        
    with st.spinner(f"Fetching live data points for {sel_stock}..."):
        pr, ema, rs, mc, hr = fetch_screener_data(sel_stock, 1)
        
    is_trade_allowed = True
    if rs is not None:
        if rs >= 60.0: st.success(f"✅ STRATEGY PASS! RSI: **{rs}** | Ready to Buy.")
        else:
            is_trade_allowed = False
            st.error(f"❌ STRATEGY BLOCK! RSI: **{rs}** | Low Momentum (RSI < 60). Trade execution locked!")
            
    with col2: ep = st.number_input("Entry Price (₹)", min_value=0.0, value=pr if pr else 100.0)
    with col3: sl = st.number_input("SL Level (20 EMA - ₹)", min_value=0.0, value=ema if ema else 95.0)
    with col4: dt = st.date_input("Entry Date", datetime.now())
        
    per_share_risk = ep - sl
    qty = int(risk_per_trade / per_share_risk) if per_share_risk > 0 else 0
    inv = qty * ep
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Dynamic Calculated Quantity", f"{qty} Shares")
    c2.metric("Investment Amount Required", f"₹{inv:,.2f}")
    c3.metric("Committed Capital Risk (1% of Total)", f"₹{risk_per_trade:,.2f}")
    
    if st.button("🚀 Execute Trade (Add to Ledger)", disabled=not is_trade_allowed):
        if not is_trade_allowed: st.error("Trade entry is strictly locked under risk parameters guidelines.")
        elif per_share_risk <= 0: st.error("Bhai, Entry Price 20 EMA SL se upar honi chahiye!")
        elif inv > current_balance: st.error("Bhai, account balance limits se bahar investment ho rahi hai!")
        else:
            new_trade = {"Status": "ACTIVE", "Stock": sel_stock, "Entry Date": dt.strftime('%Y-%m-%d'), "Entry Price": ep, "SL (20 EMA)": sl, "Qty": qty, "Investment Amt": inv, "Exit Date": "-", "Exit Price": ep, "P&L Per Share": 0.0, "Total P&L": 0.0, "Duration (Days)": 0}
            save_new_trade(current_user, new_trade)
            st.success(f"🔥 {sel_stock} trade logged in database successfully under compounding metrics!")
            st.rerun()

    # --- ACTIVE TRADES REFRESH LOGIC ---
    active_trades = [t for t in user_ledger if t["Status"] == "ACTIVE"]
    if active_trades:
        st.markdown("---")
        st.header("📡 3. Active Trades Automatic Tracking")
        for trade in active_trades:
            st.info(f"📈 **{trade['Stock']}** | Entry: ₹{trade['Entry Price']} | Qty: {trade['Qty']} | Investment: ₹{trade['Investment Amt']:,.2f}")
            exit_col1, exit_col2, exit_btn_col = st.columns([2, 2, 1])
            with exit_col1: exit_price = st.number_input(f"Actual Exit Price for {trade['Stock']}", min_value=1.0, value=float(trade['Entry Price']), key=f"ep_{trade['Trade ID']}")
            with exit_col2: exit_date = st.date_input(f"Exit Date for {trade['Stock']}", datetime.now(), key=f"ed_{trade['Trade ID']}")
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

    # --- HISTORICAL JOURNAL ---
    st.markdown("---")
    st.header("📑 4. Master Trading Ledger & Journal")
    if user_ledger:
        st.dataframe(pd.DataFrame(user_ledger)[["Status", "Stock", "Entry Date", "Entry Price", "SL (20 EMA)", "Qty", "Investment Amt", "Exit Date", "Exit Price", "P&L Per Share", "Total P&L", "Duration (Days)"]], use_container_width=True)
        if st.button("🗑️ Clear My Entire Ledger"):
            clear_user_ledger(current_user)
            st.rerun()

