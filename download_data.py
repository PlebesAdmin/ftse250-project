import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime
import os
import time

# -------------------------------------------------
# SETTINGS – change these if you want
# -------------------------------------------------
TICKERS_FILE = "Ticker.csv"          # your ticker list
DB_FILE = "ftse250_data.db"          # the SQLite database
PERIOD = "10d"                        # Changed to 10d from 1yrs
INTERVAL = "1d"                      # daily bars
BATCH_SIZE = 20                      # download in small batches (safer)

print("=" * 60)
print("FTSE 250 Data Downloader")
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# -------------------------------------------------
# 1. Load tickers
# -------------------------------------------------
if not os.path.exists(TICKERS_FILE):
    print(f"ERROR: Cannot find {TICKERS_FILE}")
    print("Make sure the file is in the same folder as this script.")
    exit()

tickers_df = pd.read_csv(TICKERS_FILE)
# Support both column names
if "Symbol" in tickers_df.columns:
    tickers = tickers_df["Symbol"].dropna().astype(str).str.strip().tolist()
elif "ticker" in tickers_df.columns:
    tickers = tickers_df["ticker"].dropna().astype(str).str.strip().tolist()
else:
    print("ERROR: Ticker.csv must have a column called 'Symbol' or 'ticker'")
    exit()

tickers = [t for t in tickers if t]   # remove empty lines
print(f"Loaded {len(tickers)} tickers from {TICKERS_FILE}")

# -------------------------------------------------
# 2. Download data in batches (more reliable)
# -------------------------------------------------
all_rows = []
failed = []

for i in range(0, len(tickers), BATCH_SIZE):
    batch = tickers[i:i + BATCH_SIZE]
    print(f"\nDownloading batch {i//BATCH_SIZE + 1} ({len(batch)} tickers)...")

    try:
        data = yf.download(
            tickers=batch,
            period=PERIOD,
            interval=INTERVAL,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False
        )

        for ticker in batch:
            try:
                if len(batch) == 1:
                    df = data.copy()
                else:
                    if ticker not in data.columns.get_level_values(0):
                        print(f"  No data returned for {ticker}")
                        failed.append(ticker)
                        continue
                    df = data[ticker].copy()

                df = df.dropna(how="all")
                if df.empty:
                    print(f"  Empty data for {ticker}")
                    failed.append(ticker)
                    continue

                df = df.reset_index()
                df["ticker"] = ticker

                # Standardise column names
                rename_map = {
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume"
                }
                df = df.rename(columns=rename_map)

                cols = ["ticker", "date", "open", "high", "low", "close", "volume"]
                df = df[[c for c in cols if c in df.columns]]

                all_rows.append(df)
                print(f"  OK: {ticker} ({len(df)} rows)")

            except Exception as e:
                print(f"  Error processing {ticker}: {e}")
                failed.append(ticker)

    except Exception as e:
        print(f"  Batch error: {e}")
        failed.extend(batch)

    time.sleep(1)   # small polite pause between batches

if not all_rows:
    print("\nNo data was downloaded. Stopping.")
    exit()

final_df = pd.concat(all_rows, ignore_index=True)
print(f"\nTotal rows prepared: {len(final_df)}")

# -------------------------------------------------
# 3. Save to SQLite (safe re-run – no duplicates)
# -------------------------------------------------
print(f"Writing to database: {DB_FILE}")

conn = sqlite3.connect(DB_FILE)

# Create table if needed
conn.execute("""
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date)
)
""")

# Insert new data (ignore rows that already exist)
final_df.to_sql("prices_temp", conn, if_exists="replace", index=False)

conn.execute("""
INSERT OR IGNORE INTO prices (ticker, date, open, high, low, close, volume)
SELECT ticker, date, open, high, low, close, volume
FROM prices_temp
""")

conn.execute("DROP TABLE IF EXISTS prices_temp")
conn.commit()

# Quick summary
summary = conn.execute("""
SELECT ticker, COUNT(*) as days
FROM prices
GROUP BY ticker
ORDER BY ticker
""").fetchall()

conn.close()

print("\n" + "=" * 60)
print("FINISHED SUCCESSFULLY")
print(f"Database now contains data for {len(summary)} tickers")
if failed:
    print(f"Failed tickers ({len(failed)}): {', '.join(failed)}")
print("=" * 60)
