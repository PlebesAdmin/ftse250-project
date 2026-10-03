import sqlite3
import pandas as pd
from datetime import datetime
import os

print("Creating weekly summary...")

if not os.path.exists("ftse250_data.db"):
    print("ERROR: Database not found")
    exit(1)

conn = sqlite3.connect("ftse250_data.db")

# Get the most recent date
latest_date = pd.read_sql_query("SELECT MAX(date) as d FROM prices", conn).iloc[0]["d"]
print(f"Latest date in database: {latest_date}")

# Load company names from Ticker.csv
try:
    tickers_df = pd.read_csv("Ticker.csv")
    # Clean column names (remove extra spaces)
    tickers_df.columns = [c.strip() for c in tickers_df.columns]
    
    # Support different possible column names
    symbol_col = None
    name_col = None
    for col in tickers_df.columns:
        if col.lower() in ["symbol", "ticker"]:
            symbol_col = col
        if "company" in col.lower() or "name" in col.lower():
            name_col = col
    
    if symbol_col and name_col:
        name_map = dict(zip(tickers_df[symbol_col].str.strip(), tickers_df[name_col].str.strip()))
    else:
        name_map = {}
        print("Warning: could not find Symbol / Company name columns")
except Exception as e:
    name_map = {}
    print(f"Warning loading names: {e}")

# Pull recent data (enough for 1 week calculation)
df = pd.read_sql_query("""
    SELECT ticker, date, close, volume
    FROM prices
    WHERE date >= date(?, '-14 days')
    ORDER BY ticker, date
""", conn, params=[latest_date])
conn.close()

summary_rows = []

for ticker, group in df.groupby("ticker"):
    group = group.sort_values("date")
    
    if len(group) < 2:
        continue
        
    latest_close = group.iloc[-1]["close"]
    latest_day = group.iloc[-1]["date"]
    
    # Roughly 5 trading days earlier
    if len(group) >= 6:
        week_ago_close = group.iloc[-6]["close"]
    else:
        week_ago_close = group.iloc[0]["close"]
    
    pct_change = ((latest_close - week_ago_close) / week_ago_close) * 100

    # Get the volume of the latest day
    latest_volume = group.iloc[-1]["volume"] if "volume" in group.columns else None
    
    summary_rows.append({
        "ticker": ticker,
        "name": name_map.get(ticker, ticker),
        "pct_change_1w": round(float(pct_change), 2),
        "latest_close": round(float(latest_close), 2),
        "week_ago_close": round(float(week_ago_close), 2),
        "latest_date": latest_day,
        "volume": int(latest_volume) if latest_volume is not None else None
    })

summary = pd.DataFrame(summary_rows)
summary = summary.sort_values("pct_change_1w", ascending=False)

filename = f"ftse250_weekly_summary_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
summary.to_excel(filename, index=False)

# Also save a JSON version for the GitHub Pages dashboard
json_filename = "summary.json"
summary.to_json(json_filename, orient="records", indent=2)

print(f"JSON summary created: {json_filename}")
print(f"Summary created: {filename}")
print(f"Tickers: {len(summary)}")
