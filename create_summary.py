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

# Pull recent data (enough for 1 week calculation)
df = pd.read_sql_query("""
    SELECT ticker, date, close
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
    
    summary_rows.append({
        "ticker": ticker,
        "latest_date": latest_day,
        "latest_close": round(float(latest_close), 2),
        "week_ago_close": round(float(week_ago_close), 2),
        "pct_change_1w": round(float(pct_change), 2)
    })

summary = pd.DataFrame(summary_rows)
summary = summary.sort_values("pct_change_1w", ascending=False)

filename = f"ftse250_weekly_summary_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
summary.to_excel(filename, index=False)

print(f"Summary created: {filename}")
print(f"Tickers: {len(summary)}")
