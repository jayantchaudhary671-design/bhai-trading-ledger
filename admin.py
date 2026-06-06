import streamlit as st
import pandas as pd
import sqlite3

def show_admin_panel():
    st.header("🛡️ Admin Panel - User Data")
    conn = sqlite3.connect("users_trading_ledger.db")
    
    st.subheader("📋 Registered Users")
    try:
        users = pd.read_sql_query("SELECT * FROM users", conn)
        st.dataframe(users)
    except: st.warning("No users found.")

    st.subheader("📊 All Trade Logs")
    try:
        trades = pd.read_sql_query("SELECT * FROM trades", conn)
        st.dataframe(trades)
    except: st.warning("No trades found.")
    
    conn.close()
