import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import sqlite3
import hashlib
import concurrent.futures

# App Settings
st.set_page_config(page_title="Bhai Ka Pro Chartink Scanner", layout="wide")

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
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hash_password(password)))
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

# --- 100% ADVANCED HISTORICAL DATA ENGINE FOR BULK SCREENING ---
def fetch_full_screener_analytics(stock_symbol, n_weeks=1):
    try:
        symbol = stock_symbol.strip().upper()
        ticker_symbol = f"{symbol}.NS"
        ticker = yf.Ticker(ticker_symbol)
        
        hist = ticker.history(period="2y", interval="1wk")
        if hist.empty or len(hist) < 20:
            ticker_symbol = f"{symbol}.BO"
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="2y", interval="1wk")
            
        if not hist.empty and len(hist) >= 20:
            hist = hist.dropna(subset=['Close'])
            hist = hist[hist['Close'] > 0]
            
            current_price = round(hist['Close'].iloc[-1], 2)
            
            # Market Cap Calculation
            mcap = ticker.info.get('marketCap', 0)
            mcap_crores = round(mcap / 10000000, 2) if mcap else 0.0
            
            # 20 EMA
            ema_series = hist['Close'].ewm(span=20, adjust=False).mean()
            current_20_ema = round(ema_series.iloc[-1], 2)
            
            # Weekly RSI Series Generator (14 Period)
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            
            current_rsi = round(rsi_series.iloc[-1], 2)
            
            return current_price, current_20_ema, current_rsi, mcap_crores
        return None, None, None, 0.0, None
    except Exception:
        return None, None, None, 0.0, None

def run_pro_bulk_screener(stock_list, n_weeks=1):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        future_to_stock = {executor.submit(fetch_full_screener_analytics, stock, n_weeks): stock for stock in stock_list}
        for future in concurrent.futures.as_completed(future_to_stock):
            stock = future_to_stock[future]
            try:
                price, ema, rsi, mcap = future.result()
                if price and rsi:
                    results.append({
                        "Stock": stock,
                        "Current Price (₹)": price,
                        "Weekly 20 EMA (₹)": ema,
                        "Current Weekly RSI": rsi,
                        "Market Cap (Cr)": mcap,
                    
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

# --- USER LOGIN SESSION SYSTEM ---
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
            if check_login(user_input, pass_input):
                st.session_state.logged_in = True
                st.session_state.current_user = user_input
                if remember_me:
                    token = save_session(user_input)
                    st.query_params["user_session_token"] = token
                st.success(f"Welcome back {user_input}!")
                st.rerun()
            else:
                st.error("Bhai, galat Username ya Password daala hai!")
    else:
        if st.button("🚀 Register & Create Account"):
            if user_input and pass_input:
                if make_signup(user_input, pass_input):
                    st.success("Account successfully created! Please switch to Login mode.")
                else:
                    st.error("Bhai, yeh Username/Mail pehle se registered hai!")
            else:
                st.error("Dono fields bharna zaroori hai!")
    st.stop()

current_user = st.session_state.current_user

# --- SIDEBAR POWERED COMPOUNDING ENGINE ---
st.sidebar.header(f"👤 User: {current_user}")
initial_capital = st.sidebar.number_input("Total Capital (₹)", min_value=100000, value=1000000, step=50000)

calculated_risk_per_trade = float(initial_capital) * 0.01
st.sidebar.metric(label="Dynamic Risk Per Trade (1% of Capital)", value=f"₹{calculated_risk_per_trade:,.2f}")

user_ledger = load_user_trades(current_user)

if st.sidebar.button("🔄 Refresh Active Trades Prices"):
    st.toast("Internet se live data sync ho raha hai...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for trade in user_ledger:
        if trade["Status"] == "ACTIVE":
            fetched_price = get_live_price(trade["Stock"])
            if fetched_price:
                pnl_sh = fetched_price - trade["Entry Price"]
                tot_pnl = pnl_sh * trade["Qty"]
                c.execute('''UPDATE trades SET exit_price=?, pnl_per_share=?, total_pnl=? WHERE id=?''', 
                          (fetched_price, pnl_sh, tot_pnl, trade["Trade ID"]))
    conn.commit()
    conn.close()
    st.rerun()

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

# --- MASTER DATABASE INDEX ---
@st.cache_data
def get_nifty_500_database():
    stocks = [
        "360ONE", "3MINDIA", "ABB", "ACC", "AIAENG", "APLAPOLLO", "AUBANK", "AARTIIND", 
        "AAVAS", "ABBOTINDIA", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ADANITOTAL", "AWL",
        "ABCAPITAL", "ABFRL", "AEGISCHEM", "AETHER", "AFFLE", "AJANTPHARM", "APLLTD", "ALKEM",
        "ALKYLAMINE", "ALLCARGO", "ALOKINDS", "ARE&M", "AMBUJACEM", "ANGELONE", "ANURAS", "APARINDS",
        "APOLLOHOSP", "APOLLOTYRE", "APTUS", "ACI", "ASIANPAINT", "ASTERDM", "ASTRAL", "ATUL",
        "AUROPHARMA", "AVANTIFEED", "DMART", "AXISBANK", "BEML", "BLS", "BSE", "BAJAJ-AUTO",
        "BAJAJFINSV", "BAJFINANCE", "BAJAJHLDNG", "BALAMINES", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA",
        "BANKINDIA", "MAHABANK", "BATAINDIA", "BAYERCROP", "BERGEPAINT", "BDL", "BEL", "BHALQ",
        "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIOCON", "BIRLACORPN", "BSOFT", "BLUEDART",
        "BORORENEW", "BOSCHLTD", "BRIGADE", "BRITANNIA", "MAPMYINDIA", "CCL", "CESC", "CGPOWER",
        "CIEINDIA", "CRISIL", "CSBBANK", "CAMPUS", "CANFINHOME", "CANBK", "CAPLIPOINT", "CGCL",
        "CARBORUNV", "CASTROLIND", "CEATLTD", "CENTRALBK", "CDSL", "CENTURYPLY", "CENTURYTEX", "CERA",
        "CHALET", "CHAMBLFERT", "CHOLAHLDNG", "CHOLAFIN", "CIPLA", "CLEAN", "COALINDIA", "COCHINSHIP",
        "COFORGE", "COLPAL", "CRAFTSMAN", "CREDITACC", "CROMPTON", "CUMMINSIND", "CYIENT", "DCAL",
        "DCBBANK", "DLF", "DABUR", "DALBHARAT", "DATAPATTNS", "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY",
        "DEVYANI", "DIVISLAB", "DIXON", "DONEAR", "ETERNAL", "LALPATHLAB", "DRREDDY", "EIDPARRY", "EIHOTEL",
        "EPL", "EASEMYTRIP", "EICHERMOT", "ELECON", "ELGIEQUIP", "EMAMILTD", "ENDOCO", "ENGINERSIN",
        "ERIS", "ESCORTSTRAC", "EXIDEIND", "FDC", "FEDERALBNK", "FACT", "FINEORG",
        "FINCABLES", "FINPIPE", "FLUOROCHEM", "FORTIS", "GRINFRA", "GAIL", "GMMPFAUDLR", "GMRINFRA",
        "GOCLCORP", "GPTINFRA", "GATEWAY", "GENUSPOWER", "GLAND", "GLAXO", "GLENMARK", "GOCOLORS",
        "GODFRYPHLP", "GODREJAGRO", "GODREJCP", "GODREJIND", "GODREJPROP", "GRANULES", "GRAPHITE", "GRASIM",
        "GESHIP", "GREENPANEL", "GRINDWELL", "GUJALKALI", "GUJGASLTD", "GMDCLTD", "GNFC", "GSFC",
        "GSPL", "HEG", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HFCL", "HLEGLAS", "HAL", "HEROMOTOCO",
        "HIKAL", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HOMEFIRST", "HONAUT",
        "HUDCO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "ISEC", "IDBI", "IDFCFIRSTB", "IDFC",
        "IIFL", "IRB", "IRCON", "IRCTC", "IRFC", "IRIS", "ITI", "INDIACEM", "INDIAMART",
        "INDIANB", "IEX", "IOC", "IOB", "INDIGO", "INDUSINDBK", "INDUSTOWER",
        "INFIBEAM", "INFY", "INGERRAND", "INOXWIND", "INTELLECT", "INDHOTEL", "IOC", "IPCALAB",
        "JBCHEPHARM", "JKCEMENT", "JKLAC", "JKPAPER", "JMFINANCIL", "JSWENERGY", "JSWINFRA", "JSWSTEEL",
        "JAIBALAJI", "JAMNAAUTO", "J&KBANK", "JINDALSAW", "JINDALPOLY", "JAL", "JINDALSTEL", "JIOFIN",
        "JUBLFOOD", "JUBLINGREA", "JUBLPHARMA", "JUSTDIAL", "JYOTHYLAB", "KIMS", "KEI", "KNRCON",
        "KPITTECH", "KRBL", "KSB", "KAJARIACER", "KALPATOGRPH", "KALYANKJIL", "KANSAINER", "KARURVYSYA",
        "KEC", "KENNAMET", "KFINTECH", "KIRLOSENG", "KIRLOSIND", "KOTAKBANK", "KREBSBIO", "KRISHANA",
        "LTFOODS", "LTIM", "LT", "LTSHRE", "LICHSGFIN", "LICI", "LAURUSLABS", "LAXMIMACH", "LEMONTREE",
        "LINDEINDIA", "LUPIN", "LUXIND", "MMTC", "MOIL", "MRF", "MTARTECH", "M&MFIN",
        "M&M", "MHRIL", "MAHLOG", "MAHSEAMLES", "MAHITH", "MANAPPURAM", "MANGCHEFER", "MRPL",
        "MARICO", "MARUTI", "MASTEK", "MAXHEALTH", "MAZDOCK", "MEDANTA",
        "MEDIASSIST", "MEDPLUS", "METROPOLIS", "MINDACORP", "MSUMI", "MOFSL", "MOLDTECH",
        "MPHASIS", "MCX", "MUTHOOTFIN", "NATCOPHARM", "NBCC", "NCC",
        "NESCO", "NFL", "NHPC", "NLCINDIA", "NMDC", "NOCIL", "NTPC", "NH",
        "NATIONALUM", "NAVINFLUOR", "NAZARA", "NEOGEN", "NESTLEIND", "NETWEB", "NETWORK18",
        "NUCLEUS", "NUVAMA", "NUVOCO", "OBEROIRLTY", "ONGC", "OIL", "OLECTRA", "OMAXE",
        "ORCHIDPHAR", "ORIENTELEC", "PFC", "PNCINFRA", "PVRINOX", "PAGEIND", "PANAMAPET",
        "PARADEEP", "PARAS", "PATANJALI", "PATELENG", "PAYTM", "PERSISTENT", "PETRONET", "PHOENIXLTD",
        "PIDILITIND", "PIIND", "PILANIINVS", "PIRPHARMA", "PEL", "POLYMED", "POLYCAB", "POLYPLEX",
        "POONAWALLA", "POWERGRID", "POWERMECH", "PRAJIND", "PRESTIGE", "PRICOLLTD", "PRINCEPIPE", "PRSMJOHNSN",
        "PRIVISCL", "PRUDENT", "QUESS", "RBLBANK", "RECLTD", "RHIM", "RITES", "RADICO",
        "RVNL", "RAILTEL", "RAIN", "RAJESHEXPO", "RALLIS", "RAMASTEEL", "RAMCOCEM", "RAMCOIND",
        "RAMCOSYS", "RATNAMANI", "RTNINDIA", "RAYMOND", "REDINGTON", "RELAXO", "RELIANCE", "RELINFRA",
        "RELPOWER", "RENUKA", "RBA", "RISHABH", "ROLEXRINGS", "ROSSARI", "ROUTE", "SBICARD",
        "SBILIFE", "SJVN", "SKFINDIA", "SRF", "SAIL", "SANSERA", "SAPPHIRE", "SAREGAMA",
        "SARDAEN", "SCHAEFFLER", "SCHNEIDER", "SEQUENT", "SHAKTIPUMP", "SHAILY", "SHALBY", "SHANKARA",
        "SHARDAMOTR", "SHARDACROP", "SHAREINDIA", "SHOPERSTOP", "SHREECEM", "SHRIRAMFIN", "SIEMENS",
        "SIGNATURE", "SOBHA", "SOLARINDS", "SONACOMS", "SONATSOFTW", "SOUTHBANK", "SPANDANA",
        "SPARC", "STARHEALTH", "SBIN", "STEELCAS", "STERTOOLS", "STLTECH", "SUMICHEM",
        "SPHARM", "SUNTV", "SUNDARMFIN", "SUNDRMFAST", "SUNTECK", "SUPRAJIT", "SUPREMEIND", 
        "SUZLON", "SWANENERGY", "SYNGENE", "SYRMA", "TEGA", "TV18BRDCST", "TVSSCS", "TVSMOTOR",
        "TVSHLTD", "TASTYBITE", "TATACHEM", "TATACOMM", "TATACONSUM", "TATAELXSI", "TATAINVEST", "TATAMOTORS",
        "TATAMTRDVR", "TATAPOWER", "TATASTEEL", "TATATECH", "TTML", "TECHM", "TECHNOE", "TEJASNET",
        "TEXRAIL", "THERMAX", "TIINDIA", "TIMKEN", "TITAN", "TORNTPOWER",
        "TORNTPHARM", "TRIDENT", "TRITURBINE", "TRIVENI", "UCOBANK", "UNOMINDA",
        "UPL", "UTIAMC", "UJJIVANSFB", "ULTRACEMCO", "UNIONBANK", "UNIPARTS", "MCDOWELL-N",
        "USHAMART", "VGUARD", "V-MART", "VIPIND", "VAIBHAVGBL", "VAKRANGEE", "VALIANTORG", "VRLLOG",
        "VBL", "VEDL", "VENKEYS", "VESUVIUS", "VOLTAS", "WELCORP", "WELSPUNLIV",
        "WESTLIFE", "WHIRLPOOL", "WIPRO", "WOCKPHARM", "WONDERLA", "XCHANGING", "YESBANK", "ZEEL",
        "ZENSARTECH", "ZYDUSLIFE", "ZYDUSWELL"
    ]
    return sorted(list(set(stocks)))

nifty_500_list = get_nifty_500_database()

# --- 🛠️ SYNTAX FIX LAYER ---
tab_screener, tab_execution = st.tabs(["📡 1. Live Momentum Screener (Pro Chartink Mode)", "🔍 2. Trade Execution Ledger"])

# --- TAB 1: THE DEDICATED PRO SCREENER ---
with tab_screener:
    st.header("🦅 Custom Real-Time Multi-Query Script Scanner")
    st.write("Apne rules ke hisab se parameters set kijiye aur Nifty 500 stocks ko instantly scan kijiye:")
    
    st.markdown("### 🛠️ 1. Configure Scanner Filters")
    c_f1, c_f2, c_f3 = st.columns(3)
    
with c_f1:

    st.subheader("Current RSI")

    enable_rsi = st.toggle(
        "Enable RSI Filter",
        value=True
    )

    rsi_min = st.number_input(
        "RSI Min",
        value=60.0
    )

    rsi_max = st.number_input(
        "RSI Max",
        value=70.0
    )

with c_f2:

    st.subheader("Universe")

    universe_size = st.selectbox(
        "Select Universe",
        [
            "Top 100",
            "Top 200",
            "Top 300",
            "Top 400",
            "Top 500"
        ]
    )

    universe_map = {
        "Top 100":100,
        "Top 200":200,
        "Top 300":300,
        "Top 400":400,
        "Top 500":500
    }

    scan_batch_limit = universe_map[universe_size]

with c_f3:

    st.subheader("Market Cap")

    enable_mcap = st.toggle(
        "Enable Market Cap Filter",
        value=False
    )

    mcap_min = st.number_input(
        "Market Cap Min (Cr)",
        value=0
    )

    mcap_max = st.number_input(
        "Market Cap Max (Cr)",
        value=99999999
    )

   
    scannable_stocks = nifty_500_list[:scan_batch_limit]
    
if st.button("🔥 Run Advanced Multi-Filter Scan"):

    with st.spinner("Processing Nifty 500 live candles... System analyzing Chartink queries..."):

        raw_matrix_results = run_pro_bulk_screener(
            scannable_stocks,
            1
        )

        filtered_matrix = []

        for item in raw_matrix_results:

            c_rsi = item["Current Weekly RSI"]

            pass_current_rsi = True

            if enable_rsi:
                pass_current_rsi = (
                    rsi_min <= c_rsi <= rsi_max
                )

            c_mcap = item["Market Cap (Cr)"]

            pass_mcap = True

            if enable_mcap:
                pass_mcap = (
                    mcap_min <= c_mcap <= mcap_max
                )

            if pass_current_rsi and pass_mcap:

                item["TradingView"] = (
                    f"https://www.tradingview.com/chart/?symbol=NSE:{item['Stock']}"
                )

                item["Screener Verification"] = "✅ MATCH APPROVED"

                filtered_matrix.append(item)
                    
            st.session_state.pro_scanner_df = pd.DataFrame(filtered_matrix)
            st.success(f"Scan Completed! Found {len(filtered_matrix)} stocks matching all specifications.")
            
    st.markdown("---")
    st.markdown("### 📋 2. Real-Time Result Grid Matrix")
    
    # 🛠️ CRITICAL STYLER FIX: Gradient rendering fallback engine to avoid Pandas 3.14 styling conflicts
    if "pro_scanner_df" in st.session_state and not st.session_state.pro_scanner_df.empty:
        df_to_show = st.session_state.pro_scanner_df.copy()
        sort_by = st.selectbox(
    "Sort Results By",
    [
        "RSI High-Low",
        "RSI Low-High",
        "Market Cap High-Low",
        "Market Cap Low-High"
    ]
)

if sort_by == "RSI High-Low":
    df_to_show = df_to_show.sort_values(
        "Current Weekly RSI",
        ascending=False
    )

elif sort_by == "RSI Low-High":
    df_to_show = df_to_show.sort_values(
        "Current Weekly RSI",
        ascending=True
    )

elif sort_by == "Market Cap High-Low":
    df_to_show = df_to_show.sort_values(
        "Market Cap (Cr)",
        ascending=False
    )

elif sort_by == "Market Cap Low-High":
    df_to_show = df_to_show.sort_values(
        "Market Cap (Cr)",
        ascending=True
    )
        try:
            styled_df = df_to_show.style.background_gradient(subset=["Current Weekly RSI", "Market Cap (Cr)"], cmap="YlGn")
            st.dataframe(styled_df, use_container_width=True)
            csv = df_to_show.to_csv(index=False)

            st.download_button(
                "📥 Export CSV",
                csv,
                "scanner_results.csv",
                "text/csv"
            )
        except Exception:
            # Fallback to absolute clean table matrix if layout gradients are un-compiled by cloud server
            st.dataframe(df_to_show, use_container_width=True)
    else:
        st.info("Scanner standby par hai. Multi-query run karne ke liye 'Run Advanced Multi-Filter Scan' dabayein.")

# --- TAB 2: POSITION SIZING ENGINE & TRADING JOURNAL ---
with tab_execution:
    st.header("🦅 Core Trade Entry System")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        stock_name = st.selectbox("Select Stock to Buy", options=nifty_500_list, index=nifty_500_list.index("SRF"))
        
    with st.spinner(f"Fetching live data points for {stock_name}..."):
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
    else:
        st.info("Ledger khali hai. Data core matrix database engine active.")

