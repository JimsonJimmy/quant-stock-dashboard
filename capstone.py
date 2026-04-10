import streamlit as st
import requests
import pandas as pd
import sqlite3

conn = sqlite3.connect('capstone.db', check_same_thread=False)
conn.execute('''
    CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY,
        ticker TEXT,
        date TEXT,
        close REAL,
        volume INTEGER,
        UNIQUE(ticker, date)
    )
''')
conn.commit()

API_KEY = st.secrets["ALPHA_VANTAGE_KEY"]

@st.cache_data(ttl=3600)
def fetch_stock(ticker):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()
    if "Time Series (Daily)" not in data:
        return None
    rows = [(ticker, date, float(v["4. close"]), int(v["5. volume"]))
            for date, v in data["Time Series (Daily)"].items()]
    conn.executemany("INSERT OR IGNORE INTO prices (ticker, date, close, volume) VALUES (?,?,?,?)", rows)
    conn.commit()
    df = pd.read_sql(f"SELECT date, close FROM prices WHERE ticker='{ticker}' ORDER BY date", conn)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    return df

st.title("📈 Quantitative Stock Dashboard")
st.write("Built by Jimson.")

ticker = st.sidebar.text_input("Stock Ticker", value="AAPL").upper()
compare = st.sidebar.text_input("Compare with (optional)", value="").upper()
fetch = st.sidebar.button("Fetch Data")

if fetch:
    with st.spinner("Fetching data..."):
        df = fetch_stock(ticker)
    if df is None:
        st.error("Could not fetch data.")
    else:
        st.session_state['df'] = df
        st.session_state['ticker'] = ticker
        if compare:
            df2 = fetch_stock(compare)
            if df2 is not None:
                st.session_state['df2'] = df2
                st.session_state['compare'] = compare

if 'df' in st.session_state:
    df = st.session_state['df']
    ticker = st.session_state['ticker']

    st.subheader(f"{ticker} Closing Price")
    if 'df2' in st.session_state:
        df2 = st.session_state['df2']
        compare = st.session_state['compare']
        df_norm = pd.DataFrame({
            ticker: df['close'] / df['close'].iloc[0] * 100,
            compare: df2['close'] / df2['close'].iloc[0] * 100
        })
        st.line_chart(df_norm)
    else:
        st.line_chart(df['close'])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current", f"${df['close'].iloc[-1]:.2f}")
    col2.metric("High", f"${df['close'].max():.2f}")
    col3.metric("Low", f"${df['close'].min():.2f}")
    returns = df['close'].pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * (252**0.5)).round(3)
    col4.metric("Sharpe Ratio", sharpe)

    st.subheader("Daily Returns (%)")
    st.line_chart(returns * 100)

    st.subheader("Statistics")
    stats = pd.DataFrame({
        'Metric': ['Avg Daily Return', 'Daily Volatility', 'Annual Volatility', 'Sharpe Ratio'],
        'Value': [
            f"{returns.mean()*100:.3f}%",
            f"{returns.std()*100:.3f}%",
            f"{returns.std()*100*(252**0.5):.2f}%",
            f"{sharpe}"
        ]
    })
    st.dataframe(stats)

    if st.checkbox("Show raw data"):
        st.dataframe(df)
