import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import sqlite3
import hashlib
import concurrent.futures

# App Config
st.set_page_config(page_title="Ultimate Trading Matrix", layout="wide")

# Database Setup
DB_FILE = "users_trading_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, status TEXT, stock TEXT, entry_date TEXT, entry_price REAL, ema_sl REAL, qty INTEGER, investment REAL, exit_date TEXT, exit_price REAL, pnl_per_share REAL, total_pnl REAL, duration INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_sessions (session_key TEXT PRIMARY KEY, username TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Session State for User Auth
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = "Guest"

# --- Engine Functions ---
@st.cache_data
def get_nifty_500():
    # Poori Nifty 500 list yahan hai
    return sorted(["360ONE", "3MINDIA", "ABB", "ACC", "AIAENG", "APLAPOLLO", "AUBANK", "AARTIIND", "AAVAS", "ABBOTINDIA", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ADANITOTAL", "AWL", "ABCAPITAL", "ABFRL", "AEGISCHEM", "AETHER", "AFFLE", "AJANTPHARM", "APLLTD", "ALKEM", "ALKYLAMINE", "ALLCARGO", "ALOKINDS", "ARE&M", "AMBUJACEM", "ANGELONE", "ANURAS", "APARINDS", "APOLLOHOSP", "APOLLOTYRE", "APTUS", "ACI", "ASIANPAINT", "ASTERDM", "ASTRAL", "ATUL", "AUROPHARMA", "AVANTIFEED", "DMART", "AXISBANK", "BEML", "BLS", "BSE", "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BAJAJHLDNG", "BALAMINES", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "MAHABANK", "BATAINDIA", "BAYERCROP", "BERGEPAINT", "BDL", "BEL", "BHALQ", "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIOCON", "BIRLACORPN", "BSOFT", "BLUEDART", "BORORENEW", "BOSCHLTD", "BRIGADE", "BRITANNIA", "MAPMYINDIA", "CCL", "CESC", "CGPOWER", "CIEINDIA", "CRISIL", "CSBBANK", "CAMPUS", "CANFINHOME", "CANBK", "CAPLIPOINT", "CGCL", "CARBORUNV", "CASTROLIND", "CEATLTD", "CENTRALBK", "CDSL", "CENTURYPLY", "CENTURYTEX", "CERA", "CHALET", "CHAMBLFERT", "CHOLAHLDNG", "CHOLAFIN", "CIPLA", "CLEAN", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL", "CRAFTSMAN", "CREDITACC", "CROMPTON", "CUMMINSIND", "CYIENT", "DCAL", "DCBBANK", "DLF", "DABUR", "DALBHARAT", "DATAPATTNS", "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY", "DEVYANI", "DIVISLAB", "DIXON", "DONEAR", "ETERNAL", "LALPATHLAB", "DRREDDY", "EIDPARRY", "EIHOTEL", "EPL", "EASEMYTRIP", "EICHERMOT", "ELECON", "ELGIEQUIP", "EMAMILTD", "ENDOCO", "ENGINERSIN", "ERIS", "ESCORTSTRAC", "EXIDEIND", "FDC", "FEDERALBNK", "FACT", "FINEORG", "FINCABLES", "FINPIPE", "FLUOROCHEM", "FORTIS", "GRINFRA", "GAIL", "GMMPFAUDLR", "GMRINFRA", "GOCLCORP", "GPTINFRA", "GATEWAY", "GENUSPOWER", "GLAND", "GLAXO", "GLENMARK", "GOCOLORS", "GODFRYPHLP", "GODREJAGRO", "GODREJCP", "GODREJIND", "GODREJPROP", "GRANULES", "GRAPHITE", "GRASIM", "GESHIP", "GREENPANEL", "GRINDWELL", "GUJALKALI", "GUJGASLTD", "GMDCLTD", "GNFC", "GSFC", "GSPL", "HEG", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HFCL", "HLEGLAS", "HAL", "HEROMOTOCO", "HIKAL", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HOMEFIRST", "HONAUT", "HUDCO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "ISEC", "IDBI", "IDFCFIRSTB", "IDFC", "IIFL", "IRB", "IRCON", "IRCTC", "IRFC", "IRIS", "ITI", "INDIACEM", "INDIAMART", "INDIANB", "IEX", "IOC", "IOB", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFIBEAM", "INFY", "INGERRAND", "INOXWIND", "INTELLECT", "INDHOTEL", "IPCALAB", "JBCHEPHARM", "JKCEMENT", "JKLAC", "JKPAPER", "JMFINANCIL", "JSWENERGY", "JSWINFRA", "JSWSTEEL", "JAIBALAJI", "JAMNAAUTO", "J&KBANK", "JINDALSAW", "JINDALPOLY", "JAL", "JINDALSTEL", "JIOFIN", "JUBLFOOD", "JUBLINGREA", "JUBLPHARMA", "JUSTDIAL", "JYOTHYLAB", "KIMS", "KEI", "KNRCON", "KPITTECH", "KRBL", "KSB", "KAJARIACER", "KALPATOGRPH", "KALYANKJIL", "KANSAINER", "KARURVYSYA", "KEC", "KENNAMET", "KFINTECH", "KIRLOSENG", "KIRLOSIND", "KOTAKBANK", "KREBSBIO", "KRISHANA", "LTFOODS", "LTIM", "LT", "LTSHRE", "LICHSGFIN", "LICI", "LAURUSLABS", "LAXMIMACH", "LEMONTREE", "LINDEINDIA", "LUPIN", "LUXIND", "MMTC", "MOIL", "MRF", "MTARTECH", "M&MFIN", "M&M", "MHRIL", "MAHLOG", "MAHSEAMLES", "MAHITH", "MANAPPURAM", "MANGCHEFER", "MRPL", "MARICO", "MARUTI", "MASTEK", "MAXHEALTH", "MAZDOCK", "MEDANTA", "MEDIASSIST", "MEDPLUS", "METROPOLIS", "MINDACORP", "MSUMI", "MOFSL", "MOLDTECH", "MPHASIS", "MCX", "MUTHOOTFIN", "NATCOPHARM", "NBCC", "NCC", "NESCO", "NFL", "NHPC", "NLCINDIA", "NMDC", "NOCIL", "NTPC", "NH", "NATIONALUM", "NAVINFLUOR", "NAZARA", "NEOGEN", "NESTLEIND", "NETWEB", "NETWORK18", "NUCLEUS", "NUVAMA", "NUVOCO", "OBEROIRLTY", "ONGC", "OIL", "OLECTRA", "OMAXE", "ORCHIDPHAR", "ORIENTELEC", "PFC", "PNCINFRA", "PVRINOX", "PAGEIND", "PANAMAPET", "PARADEEP", "PARAS", "PATANJALI", "PATELENG", "PAYTM", "PERSISTENT", "PETRONET", "PHOENIXLTD", "PIDILITIND", "PIIND", "PILANIINVS", "PIRPHARMA", "PEL", "POLYMED", "POLYCAB", "POLYPLEX", "POONAWALLA", "POWERGRID", "POWERMECH", "PRAJIND", "PRESTIGE", "PRICOLLTD", "PRINCEPIPE", "PRSMJOHNSN", "PRIVISCL", "PRUDENT", "QUESS", "RBLBANK", "RECLTD", "RHIM", "RITES", "RADICO", "RVNL", "RAILTEL", "RAIN", "RAJESHEXPO", "RALLIS", "RAMASTEEL", "RAMCOCEM", "RAMCOIND", "RAMCOSYS", "RATNAMANI", "RTNINDIA", "RAYMOND", "REDINGTON", "RELAXO", "RELIANCE", "RELINFRA", "RELPOWER", "RENUKA", "RBA", "RISHABH", "ROLEXRINGS", "ROSSARI", "ROUTE", "SBICARD", "SBILIFE", "SJVN", "SKFINDIA", "SRF", "SAIL", "SANSERA", "SAPPHIRE", "SAREGAMA", "SARDAEN", "SCHAEFFLER", "SCHNEIDER", "SEQUENT", "SHAKTIPUMP", "SHAILY", "SHALBY", "SHANKARA", "SHARDAMOTR", "SHARDACROP", "SHAREINDIA", "SHOPERSTOP", "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SIGNATURE", "SOBHA", "SOLARINDS", "SONACOMS", "SONATSOFTW", "SOUTHBANK", "SPANDANA", "SPARC", "STARHEALTH", "SBIN", "STEELCAS", "STERTOOLS", "STLTECH", "SUMICHEM", "SPHARM", "SUNTV", "SUNDARMFIN", "SUNDRMFAST", "SUNTECK", "SUPRAJIT", "SUPREMEIND", "SUZLON", "SWANENERGY", "SYNGENE", "SYRMA", "TEGA", "TV18BRDCST", "TVSSCS", "TVSMOTOR", "TVSHLTD", "TASTYBITE", "TATACHEM", "TATACOMM", "TATACONSUM", "TATAELXSI", "TATAINVEST", "TATAMOTORS", "TATAMTRDVR", "TATAPOWER", "TATASTEEL", "TATATECH", "TTML", "TECHM", "TECHNOE", "TEJASNET", "TEXRAIL", "THERMAX", "TIINDIA", "TIMKEN", "TITAN", "TORNTPOWER", "TORNTPHARM", "TRIDENT", "TRITURBINE", "TRIVENI", "UCOBANK", "UNOMINDA", "UPL", "UTIAMC", "UJJIVANSFB", "ULTRACEMCO", "UNIONBANK", "UNIPARTS", "MCDOWELL-N", "USHAMART", "VGUARD", "V-MART", "VIPIND", "VAIBHAVGBL", "VAKRANGEE", "VALIANTORG", "VRLLOG", "VBL", "VEDL", "VENKEYS", "VESUVIUS", "VOLTAS", "WELCORP", "WELSPUNLIV", "WESTLIFE", "WHIRLPOOL", "WIPRO", "WOCKPHARM", "WONDERLA", "XCHANGING", "YESBANK", "ZEEL", "ZENSARTECH", "ZYDUSLIFE", "ZYDUSWELL"])

nifty_500_list = get_nifty_500()

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
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_stock = {executor.submit(fetch_screener_data, stock, n_weeks): stock for stock in stock_list}
        for future in concurrent.futures.as_completed(future_to_stock):
            stock = future_to_stock[future]
            price, ema, rsi, mcap, hist_rsi = future.result()
            if price:
                results.append({"Stock": stock, "Price (₹)": price, "Current RSI": rsi, "Market Cap (Cr)": mcap, f"{n_weeks} Wks Ago RSI": hist_rsi})
    return results

# --- UI Setup ---
st.title("🦅 Ultimate Chartink Scanner & Execution")
tab_scan, tab_exec = st.tabs(["📡 Screener Matrix", "🔍 Trade Execution"])

if "target_stock" not in st.session_state: st.session_state.target_stock = "SRF"

with tab_scan:
    st.markdown("### 🛠️ Config Filters")
    
    # Bucket Selection
    bucket = st.selectbox("Select Market Cap Universe", ["Top 100", "Top 200", "Top 300", "Top 400", "All 500"])
    limit = int(bucket.split()[1]) if "Top" in bucket else len(nifty_500_list)
    scan_pool = nifty_500_list[:limit]

    # Filters layout exactly like Chartink (Side-by-Side)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        en_gt = st.checkbox("Enable RSI >")
        val_gt = st.number_input("Min RSI", value=60.0, disabled=not en_gt)
    with c2:
        en_lt = st.checkbox("Enable RSI <")
        val_lt = st.number_input("Max RSI", value=75.0, disabled=not en_lt)
    with c3:
        en_h = st.checkbox("Enable Hist RSI")
        n_weeks = st.number_input("N Weeks Ago", value=4, disabled=not en_h)
        h_dir = st.selectbox("Hist Condition", ["More Than (>)", "Less Than (<)"], disabled=not en_h)
        h_val = st.number_input("Hist RSI Value", value=50.0, disabled=not en_h)
    with c4:
        en_mcap = st.checkbox("Enable Market Cap")
        mcap_dir = st.selectbox("MCap Condition", ["More Than (>)", "Less Than (<)"], disabled=not en_mcap)
        mcap_val = st.number_input("MCap Value (Cr)", value=20000.0, disabled=not en_mcap)

    if st.button("🔥 Run Scan on Selected Universe"):
        with st.spinner(f"Scanning {limit} stocks... Please wait."):
            raw = run_screener(scan_pool, n_weeks)
            df = pd.DataFrame(raw)
            
            if not df.empty:
                # Apply all enabled filters
                if en_gt: df = df[df["Current RSI"] > val_gt]
                if en_lt: df = df[df["Current RSI"] < val_lt]
                if en_h:
                    if "More Than" in h_dir: df = df[df[f"{n_weeks} Wks Ago RSI"] > h_val]
                    else: df = df[df[f"{n_weeks} Wks Ago RSI"] < h_val]
                if en_mcap:
                    if "More Than" in mcap_dir: df = df[df["Market Cap (Cr)"] > mcap_val]
                    else: df = df[df["Market Cap (Cr)"] < mcap_val]
                
                st.success(f"Scan Finished! Found {len(df)} matching stocks.")
                
                # Interface Table Output
                st.markdown("---")
                h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1, 1, 1.5, 1.5, 1.5])
                h1.write("**Stock**"); h2.write("**Price(₹)**"); h3.write("**RSI**"); h4.write("**Market Cap (Cr)**"); h5.write("**Chart**"); h6.write("**Action**")
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
                        st.toast(f"{row['Stock']} selected! Go to Trade Execution Tab.")
            else:
                st.warning("No data found for the selected universe.")

with tab_exec:
    st.header("Trade Execution Module")
    # Form logic
    if st.session_state.target_stock not in nifty_500_list: nifty_500_list.append(st.session_state.target_stock)
    sel_stock = st.selectbox("Stock to Execute", nifty_500_list, index=nifty_500_list.index(st.session_state.target_stock))
    
    st.write(f"Pre-filled logic for {sel_stock} will go here based on your capital.")

