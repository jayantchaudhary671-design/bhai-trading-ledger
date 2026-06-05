import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import sqlite3
import hashlib

# App Settings
st.set_page_config(page_title="Bhai Ka Multi-User Terminal", layout="wide")

# --- DATABASE SETUP (SQLITE) FOR MULTI-USERS ---
DB_FILE = "users_trading_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users Credentials Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Trades Ledger Table linked with Username
    c.execute('''CREATE TABLE IF NOT EXISTS trades 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, status TEXT, 
                  stock TEXT, entry_date TEXT, entry_price REAL, ema_sl REAL, 
                  qty INTEGER, investment REAL, exit_date TEXT, exit_price REAL, 
                  pnl_per_share REAL, total_pnl REAL, duration INTEGER)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

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

def check_login(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result

def load_user_trades(username):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM trades WHERE username=?", conn, params=(username,))
    conn.close()
    if not df.empty:
        # Format mapping to match old ledger style
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

# Initialize Database on boot
init_db()

# --- LOGIN / SIGNUP SCREEN INTERFACE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

if not st.session_state.logged_in:
    st.title("🔒 Terminal Login / Signup Portal")
    auth_mode = st.radio("Choose Action", ["Login Existing Account", "Create New Account (Signup)"])
    
    user_input = st.text_input("Enter Username / Mail ID").strip()
    pass_input = st.text_input("Enter Password", type="password")
    
    if auth_mode == "Login Existing Account":
        if st.button("🔐 Login"):
            if check_login(user_input, pass_input):
                st.session_state.logged_in = True
                st.session_state.current_user = user_input
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
    st.stop() # Stops application flow here until user logs in

# --- ACTUAL APP STARTS AFTER SUCCESSFUL LOGIN ---
current_user = st.session_state.current_user

# Sidebar configuration with Logout Option
st.sidebar.header(f"👤 User: {current_user}")
if st.sidebar.button("🚪 Logout Account"):
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.rerun()

st.title("🦅 Full-Scale Nifty 500 Multi-User Automated Trading Ledger")
st.write(f"Strict ₹10,000 Risk Engine linked dynamically to user session.")

# Load specific user data from SQLite Database
user_ledger = load_user_trades(current_user)

# --- MASTER DATABASE: ALL NIFTY 500 STOCKS ---
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
        "DEVYANI", "DIVISLAB", "DIXON", "DONEAR", "LALPATHLAB", "DRREDDY", "EIDPARRY", "EIHOTEL",
        "EPL", "EASEMYTRIP", "EICHERMOT", "ELECON", "ELGIEQUIP", "EMAMILTD", "ENDOCO", "ENGINERSIN",
        "ERIS", "ESCORTSTRAC", "EXIDEIND", "FDC", "FSNKYND (NYKAA)", "FEDERALBNK", "FACT", "FINEORG",
        "FINCABLES", "FINPIPE", "FLUOROCHEM", "FORTIS", "GRINFRA", "GAIL", "GMMPFAUDLR", "GMRINFRA",
        "GOCLCORP", "GPTINFRA", "GATEWAY", "GENUSPOWER", "GLAND", "GLAXO", "GLENMARK", "GOCOLORS",
        "GODFRYPHLP", "GODREJAGRO", "GODREJCP", "GODREJIND", "GODREJPROP", "GRANULES", "GRAPHITE", "GRASIM",
        "GESHIP", "GREENPANEL", "GRINDWELL", "GUJALKALI", "GUJGASLTD", "GMDCLTD", "GNFC", "GSFC",
        "GSPL", "HEG", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HFCL", "HLEGLAS", "HAL", "HEROMOTOCO",
        "HIKAL", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HOMEFIRST", "HONAUT",
        "HUDCO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "ISEC", "IDBI", "IDFCFIRSTB", "IDFC",
        "IIFL", "IRB", "IRCON", "IRCTC", "IRFC", "IRIS", "ITI", "INDIACEM", "INDIAMART",
        "INDIANB", "IEX", "IOC", "IOB", "INDIGO", "INDUSINDBK", "INDUSTOWER",
        "INFIBEAM", "INFY", "INGERRAND", "INOXWIND", "INTELLECT", "INDHOTEL", "IPCALAB",
        "JBCHEPHARM", "JKCEMENT", "JKLAC", "JKPAPER", "JMFINANCIL", "JSWENERGY", "JSWINFRA", "JSWSTEEL",
        "JAIBALAJI", "JAMNAAUTO", "J&KBANK", "JINDALSAW", "JINDALPOLY", "JAL", "JINDALSTEL", "JIOFIN",
        "JUBLFOOD", "JUBLINGREA", "JUBLPHARMA", "JUSTDIAL", "JYOTHYLAB", "KIMS", "KEI", "KNRCON",
        "KPITTECH", "KRBL", "KSB", "KAJARIACER", "KALPATOGRPH", "KALYANKJIL", "KANSAINER", "KARURVYSYA",
        "KEC", "KENNAMET", "KFINTECH", "KIRLOSENG", "KIRLOSIND", "KOTAKBANK", "KREBSBIO", "KRISHANA",
        "LTFOODS", "LTIM", "LT", "LTSHRE", "LICHSGFIN", "LICI", "LAURUSLABS", "LAXMIMACH", "LEMONTREE",
        "LINDEINDIA", "LUPIN", "LUXIND", "MMTC", "MOIL", "MRF", "MTARTECH", "M&MFIN",
        "M&M", "MHRIL", "MAHLOG", "MAHSEAMLES", "MAHITH", "MANAPPURAM", "MANGCHEFER", "MRPL",
        "MARICO", "MARUTI", "MASTEK", "MASTERS", "MATRIMONY", "MAXHEALTH", "MAZDOCK", "MEDANTA",
        "MEDIASSIST", "MEDPLUS", "METROPOLIS", "MINDACORP", "MSUMI", "MITSU", "MOFSL", "MOLDTECH",
        "MOTHERSUMI", "MOTOROD", "MPHASIS", "MCX", "MUTHOOTFIN", "NATCOPHARM", "NBCC", "NCC",
        "NESCO", "NFL", "NHPC", "NLCINDIA", "NMDC", "NOCIL", "NTPC", "NH",
        "NATIONALUM", "NAVINFLUOR", "NAZARA", "NEOGEN", "NESF", "NESTLEIND", "NETWEB", "NETWORK18",
        "NUCLEUS", "NUVAMA", "NUVOCO", "OBEROIRLTY", "ONGC", "OIL", "OLECTRA", "OMAXE",
        "OPTIMUS", "ORCHIDPHAR", "ORIENTELEC", "PFC", "PNCINFRA", "PVRINOX", "PAGEIND", "PANAMAPET",
        "PARADEEP", "PARAS", "PATANJALI", "PATELENG", "PAYTM", "PERSISTENT", "PETRONET", "PHOENIXLTD",
        "PIDILITIND", "PIIND", "PILANIINVS", "PIRPHARMA", "PEL", "POLYMED", "POLYCAB", "POLYPLEX",
        "POONAWALLA", "POWERGRID", "POWERMECH", "PRAJIND", "PRESTIGE", "PRICOLLTD", "PRINCEPIPE", "PRSMJOHNSN",
        "PRIVISCL", "PRUDENT", "QUESS", "RBLBANK", "RECLTD", "RHIM", "RITES", "RADICO",
        "RVNL", "RAILTEL", "RAIN", "RAJESHEXPO", "RALLIS", "RAMASTEEL", "RAMCOCEM", "RAMCOIND",
        "RAMCOSYS", "RATNAMANI", "RTNINDIA", "RAYMOND", "REDINGTON", "RELAXO", "RELIANCE", "RELINFRA",
        "RELPOWER", "RENUKA", "RBA", "RISHABH", "ROLEXRINGS", "ROSSARI", "ROUTE", "SBICARD",
        "SBILIFE", "SJVN", "SKFINDIA", "SRF", "SAIL", "SANSERA", "SAPPHIRE", "SAREGAMA",
        "SARDAEN", "SCHAEFFLER", "SCHNEIDER", "SEQUENT", "SHAKTIPUMP", "SHAILY", "SHALBY", "SHANKARA",
        "SHARDAMOTR", "SHARDACROP", "SHAREINDIA", "SHOPERSTOP", "SHREECEM", "RENUKA", "SHRIRAMFIN", "SIEMENS",
        "SIGNATURE", "SILVERQ", "SOBHA", "SOLARINDS", "SONACOMS", "SONATSOFTW", "SOUTHBANK", "SPANDANA",
        "SPARC", "SRHHL", "STARHEALTH", "SBIN", "STEELCAS", "STERTOOLS", "STLTECH", "SUMICHEM",
        "SPHARM", "SUNTV", "SUNDARMFIN", "SUNDRMFAST", "SUNTECK", "SUPRAJIT", "SUPREMEIND", "SUPREMEENG",
        "SUZLON", "SWANENERGY", "SYNGENE", "SYRMA", "TEGA", "TV18BRDCST", "TVSSCS", "TVSMOTOR",
        "TVSHLTD", "TASTYBITE", "TATACHEM", "TATACOMM", "TATACONSUM", "TATAELXSI", "TATAINVEST", "TATAMOTORS",
        "TATAMTRDVR", "TATAPOWER", "TATASTEEL", "TATATECH", "TTML", "TECHM", "TECHNOE", "TEJASNET",
        "TEXRAIL", "THERMAX", "THGROUP", "THYROCARE", "TIINDIA", "TIMKEN", "TITAN", "TORNTPOWER",
        "TORNTPHARM", "TREXIND", "TRIDENT", "TRITURBINE", "TRIVENI", "TRU", "UCOBANK", "UNOMINDA",
        "UPL", "UTIAMC", "UJJIVANSFB", "ULTRACEMCO", "UNIONBANK", "UNIPARTS", "UNITEDTEA", "MCDOWELL-N",
        "USHAMART", "VGUARD", "V-MART", "VIPIND", "VAIBHAVGBL", "VAKRANGEE", "VALIANTORG", "VRLLOG",
        "VBL", "VEDL", "VENKEYS", "VESUVIUS", "VESTIND", "VOLTAS", "WELCORP", "WELSPUNLIV",
        "WESTLIFE", "WHIRLPOOL", "WIPRO", "WOCKPHARM", "WONDERLA", "XCHANGING", "YESBANK", "ZEEL",
        "ZENSARTECH", "ZOMATO", "ZYDUSLIFE", "ZYDUSWELL"
    ]
    return sorted(list(set(stocks)))

nifty_500_list = get_nifty_500_database()
fix_risk_amount = 10000.0

# --- FUNCTION: AUTOMATIC LIVE PRICE FETCH ---
def get_live_price(stock_symbol):
    try:
        ticker_symbol = f"{stock_symbol.strip().upper()}.NS"
        ticker = yf.Ticker(ticker_symbol)
        todays_data = ticker.history(period='1d')
        if not todays_data.empty:
            return round(todays_data['Close'].iloc[-1], 2)
        else:
            ticker_symbol_bse = f"{stock_symbol.strip().upper()}.BO"
            ticker_bse = yf.Ticker(ticker_symbol_bse)
            todays_data_bse = ticker_bse.history(period='1d')
            if not todays_data_bse.empty:
                return round(todays_data_bse['Close'].iloc[-1], 2)
            return None
    except Exception as e:
        return None

# --- SIDEBAR: ACCOUNT SUMMARY METRICS ---
st.sidebar.header("💰 Balance Metrics")
initial_capital = st.sidebar.number_input("Total Capital (₹)", min_value=100000, value=1000000, step=50000)

if st.sidebar.button("🔄 Refresh Automatic Daily Prices"):
    st.toast("Internet se live data sync ho rha hai...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for trade in user_ledger:
        if trade["Status"] == "ACTIVE":
            fetched_price = get_live_price(trade["Stock"])
            if fetched_price:
                pnl_sh = fetched_price - trade["Entry Price"]
                tot_pnl = pnl_sh * trade["Qty"]
                c.execute('''UPDATE trades SET exit_price=?, pnl_per_share=?, total_pnl=? 
                             WHERE id=?''', (fetched_price, pnl_sh, tot_pnl, trade["Trade ID"]))
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

# --- SECTION 1: LOG NEW ENTRY ---
st.header("🔍 1. Log New Trade Entry")
col1, col2, col3, col4 = st.columns(4)

with col1:
    selected_stock = st.selectbox("Select Stock (Nifty 500 Database)", options=nifty_500_list, index=nifty_500_list.index("SRF"))
    allow_custom = st.checkbox("🔍 Manual entry (Penny/Custom Stock)")
    stock_name = st.text_input("Custom Ticker Name", value="").upper() if allow_custom else selected_stock

with col2:
    entry_price = st.number_input("Entry Price (₹)", min_value=1.0, value=2700.0)
with col3:
    ema_20_sl = st.number_input("SL Level (20 EMA - ₹)", min_value=1.0, value=2650.0)
with col4:
    entry_date = st.date_input("Entry Date", datetime.now())

per_share_risk = entry_price - ema_20_sl
qty = int(fix_risk_amount / per_share_risk) if per_share_risk > 0 else 0
investment_amt = qty * entry_price

c1, c2, c3 = st.columns(3)
c1.metric("Calculated Quantity", f"{qty} Shares")
c2.metric("Investment Amount Required", f"₹{investment_amt:,.2f}")
c3.metric("Committed Risk (Strict)", f"₹{fix_risk_amount if qty > 0 else 0:,}")

if st.button("🚀 Execute Trade (Add to Ledger)"):
    if not stock_name:
        st.error("Bhai, stock symbol daalna zaroori hai!")
    elif per_share_risk <= 0:
        st.error("Bhai, Entry Price 20 EMA SL se upar honi chahiye!")
    elif investment_amt > current_balance:
        st.error("Bhai, account mein itna capital nahi hai!")
    else:
        with st.spinner("Internet se validation ho raha hai..."):
            live_price_now = get_live_price(stock_name)
        live_price_now = live_price_now if live_price_now else entry_price
        
        new_trade = {
            "Status": "ACTIVE", "Stock": stock_name, "Entry Date": entry_date.strftime('%Y-%m-%d'),
            "Entry Price": entry_price, "SL (20 EMA)": ema_20_sl, "Qty": qty, "Investment Amt": investment_amt,
            "Exit Date": "-", "Exit Price": live_price_now, "P&L Per Share": live_price_now - entry_price,
            "Total P&L": (live_price_now - entry_price) * qty, "Duration (Days)": 0
        }
        save_new_trade(current_user, new_trade)
        st.success(f"🔥 Trade logged successfully under session user '{current_user}'!")
        st.rerun()

# --- SECTION 2: AUTO PRICE MONITOR & EXIT PANEL ---
active_trades = [t for t in user_ledger if t["Status"] == "ACTIVE"]
if active_trades:
    st.markdown("---")
    st.header("📡 2. Active Trades Automatic Tracking")
    
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

# --- SECTION 3: THE MASTER JOURNAL ---
st.markdown("---")
st.header("📑 3. Master Trading Ledger & Journal")

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
    st.info("Abhi aapka personal ledger khali hai. Koi trade add kijiye!")