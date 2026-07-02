import pandas as pd
import numpy as np
import http.client
import json
import ssl
import os

# Disable SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

# Create output directory
OUTPUT_DIR = r"C:\Users\ArumuPuv\dhan_test\data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========================================
# AISSR5sss Strategy — Python Implementation
# (TMA Envelope + Heikin Ashi Signals)
# ========================================

# === CONFIGURATION (matches Pine Script inputs) ===
TMA_LENGTH = 51
ENVELOPE_PCT = 0.10       # 0.10%
INITIAL_CAPITAL = 1000000  # Starting capital
ENTRY_QTY = 12             # Adjust for your instrument
TP1_QTY = 6              # Fraction of entry_qty to close at TP1
TP2_QTY = 3            # Fraction of entry_qty to close at TP2
LOT_SIZE = 250            # 1 lot = 1 unit for BTCUSDT
IS_HEIKIN_ASHI = False    # True = input data is already Heikin Ashi, False = convert normal candles to HA
INPUT_TIMEFRAME = 1      # Input candle timeframe in minutes (e.g., 3, 5, 15, 20)
CANDLE_TIMEFRAME = 15     # Desired output candle timeframe in minutes
CONVERT_TIMEFRAME = True # True = convert INPUT_TIMEFRAME to CANDLE_TIMEFRAME, False = use as-is

# === 1. READ DATA FROM DHAN API ===
conn = http.client.HTTPSConnection("api.dhan.co")
payload = json.dumps({
    "securityId": "538686",
    "exchangeSegment": "MCX_COMM",
    "instrument": "FUTCOM",
    "interval": "15",
    "oi": "false",
    "fromDate": "2026-06-23",
    "toDate": "2026-07-02"
})
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'access-token': 'xxx'
}
conn.request("POST", "/v2/charts/intraday", payload, headers)
res = conn.getresponse()
data = json.loads(res.read().decode("utf-8"))

# Save raw response to file
response_file = os.path.join(OUTPUT_DIR, "dhan_response.json")
with open(response_file, "w") as f:
    json.dump(data, f, indent=2)
print(f"Raw API response saved to {response_file}")

# Parse API response into DataFrame
df = pd.DataFrame({
    "Date": pd.to_datetime(data["timestamp"], unit="s", utc=True).tz_convert("Asia/Kolkata"),
    "Open": data["open"],
    "High": data["high"],
    "Low": data["low"],
    "Close": data["close"],
    "Volume": data["volume"]
})
df.sort_values("Date", inplace=True)
df.reset_index(drop=True, inplace=True)

# Save OHLCV data to CSV
ohlcv_file = os.path.join(OUTPUT_DIR, "dhan_ohlcv_data.csv")
df.to_csv(ohlcv_file, index=False)
print(f"OHLCV data saved to {ohlcv_file} ({len(df)} rows)")

# Ensure numeric columns
for col in ["Open", "High", "Low", "Close", "Volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# === 1.5. TIMEFRAME CONVERSION ===
if CONVERT_TIMEFRAME and CANDLE_TIMEFRAME != INPUT_TIMEFRAME:
    if CANDLE_TIMEFRAME % INPUT_TIMEFRAME != 0:
        raise ValueError(f"CANDLE_TIMEFRAME ({CANDLE_TIMEFRAME}) must be a multiple of INPUT_TIMEFRAME ({INPUT_TIMEFRAME})")
    df.set_index("Date", inplace=True)
    rule = f"{CANDLE_TIMEFRAME}min"
    df = df.resample(rule).agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna().reset_index()
    print(f"Converted {INPUT_TIMEFRAME}m candles -> {CANDLE_TIMEFRAME}m candles ({len(df)} rows)")

# === 2. HEIKIN ASHI CONVERSION ===
if IS_HEIKIN_ASHI:
    df["HA_Open"] = df["Open"]
    df["HA_High"] = df["High"]
    df["HA_Low"] = df["Low"]
    df["HA_Close"] = df["Close"]
else:
    df["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    df["HA_Open"] = 0.0
    df.loc[0, "HA_Open"] = df.loc[0, "Open"]
    for i in range(1, len(df)):
        df.loc[i, "HA_Open"] = (df.loc[i - 1, "HA_Open"] + df.loc[i - 1, "HA_Close"]) / 2
    df["HA_High"] = df[["High", "HA_Open", "HA_Close"]].max(axis=1)
    df["HA_Low"] = df[["Low", "HA_Open", "HA_Close"]].min(axis=1)

# Save Heikin Ashi candles to CSV
ha_df = df[["Date", "HA_Open", "HA_High", "HA_Low", "HA_Close", "Volume"]].copy()
ha_df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
ha_file = os.path.join(OUTPUT_DIR, "NG_heikin_ashi.csv")
ha_df.to_csv(ha_file, index=False)
print(f"Heikin Ashi data saved to {ha_file} ({len(ha_df)} rows)")

# === 3. TMA + ENVELOPE ===
# TMA = SMA of SMA (triangular moving average)
sma1 = df["Close"].rolling(window=TMA_LENGTH, min_periods=TMA_LENGTH).mean()
df["TMA"] = sma1.rolling(window=TMA_LENGTH, min_periods=TMA_LENGTH).mean()
df["Upper_Env"] = df["TMA"] * (1 + ENVELOPE_PCT / 100)
df["Lower_Env"] = df["TMA"] * (1 - ENVELOPE_PCT / 100)

# === 4. SIGNAL CONDITIONS ===
# Bull: all HA OHLC above upper envelope
df["Bull_Signal"] = (
    (df["HA_Open"] > df["Upper_Env"])
    & (df["HA_High"] > df["Upper_Env"])
    & (df["HA_Low"] > df["Upper_Env"])
    & (df["HA_Close"] > df["Upper_Env"])
)
# Bear: all HA OHLC below lower envelope
df["Bear_Signal"] = (
    (df["HA_Open"] < df["Lower_Env"])
    & (df["HA_High"] < df["Lower_Env"])
    & (df["HA_Low"] < df["Lower_Env"])
    & (df["HA_Close"] < df["Lower_Env"])
)

# === 4.5 EXPORT TMA & HEIKIN ASHI VALUES ===
export_df = df[[
    "Date", "Open", "High", "Low", "Close", "Volume",
    "HA_Open", "HA_High", "HA_Low", "HA_Close",
    "TMA", "Upper_Env", "Lower_Env",
    "Bull_Signal", "Bear_Signal"
]].copy()

# Format signal columns as YES/NO for readability
export_df["Bull_Signal"] = export_df["Bull_Signal"].apply(lambda x: "YES" if x else "NO")
export_df["Bear_Signal"] = export_df["Bear_Signal"].apply(lambda x: "YES" if x else "NO")

# Format numeric columns to 2 decimal places
for col in ["Open", "High", "Low", "Close", "HA_Open", "HA_High", "HA_Low", "HA_Close", "TMA", "Upper_Env", "Lower_Env"]:
    export_df[col] = export_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")

tma_file = os.path.join(OUTPUT_DIR, "TMA_HEIKIN_ASHI_VALUES.csv")
export_df.to_csv(tma_file, index=False)
print(f"TMA & Heikin Ashi values saved to {tma_file} ({len(export_df)} rows)")

# === 5. STRATEGY SIMULATION ===
trades = []          # Completed trade log
capital = INITIAL_CAPITAL  # Running capital
position = 0         # +1 = long, -1 = short, 0 = flat
entry_price = 0.0
signal_state = 0     # 0 = idle, 1 = pending long, -1 = pending short
sig_high = np.nan
sig_low = np.nan
sig_range = 0.0
target1 = np.nan
target2 = np.nan
tp1_hit = False
tp2_hit = False
entry_date = None
remaining_qty = 0.0

for i in range(len(df)):
    if np.isnan(df["TMA"].iloc[i]):
        continue

    row = df.iloc[i]
    bull = row["Bull_Signal"]
    bear = row["Bear_Signal"]
    high = row["High"]
    low = row["Low"]
    close = row["Close"]

    # --- CHECK TP TARGETS IF IN POSITION ---
    if position == 1:  # Long
        if not tp1_hit and not np.isnan(target1) and high >= target1:
            tp1_hit = True
            closed_qty = min(TP1_QTY, remaining_qty)
            remaining_qty -= closed_qty
            pnl = (target1 - entry_price) * closed_qty * LOT_SIZE
            capital += pnl
            trades.append({
                "Entry_Date": entry_date, "Exit_Date": row["Date"],
                "Direction": "LONG", "Entry_Price": entry_price,
                "Exit_Price": target1, "Qty": closed_qty,
                "PnL": pnl, "Capital": capital,
                "Exit_Reason": "TP1"
            })
        if not tp2_hit and not np.isnan(target2) and high >= target2:
            tp2_hit = True
            closed_qty = min(TP2_QTY, remaining_qty)
            remaining_qty -= closed_qty
            pnl = (target2 - entry_price) * closed_qty * LOT_SIZE
            capital += pnl
            trades.append({
                "Entry_Date": entry_date, "Exit_Date": row["Date"],
                "Direction": "LONG", "Entry_Price": entry_price,
                "Exit_Price": target2, "Qty": closed_qty,
                "PnL": pnl, "Capital": capital,
                "Exit_Reason": "TP2"
            })
        if remaining_qty <= 0:
            position = 0
            signal_state = 0

    elif position == -1:  # Short
        if not tp1_hit and not np.isnan(target1) and low <= target1:
            tp1_hit = True
            closed_qty = min(TP1_QTY, remaining_qty)
            remaining_qty -= closed_qty
            pnl = (entry_price - target1) * closed_qty * LOT_SIZE
            capital += pnl
            trades.append({
                "Entry_Date": entry_date, "Exit_Date": row["Date"],
                "Direction": "SHORT", "Entry_Price": entry_price,
                "Exit_Price": target1, "Qty": closed_qty,
                "PnL": pnl, "Capital": capital,
                "Exit_Reason": "TP1"
            })
        if not tp2_hit and not np.isnan(target2) and low <= target2:
            tp2_hit = True
            closed_qty = min(TP2_QTY, remaining_qty)
            remaining_qty -= closed_qty
            pnl = (entry_price - target2) * closed_qty * LOT_SIZE
            capital += pnl
            trades.append({
                "Entry_Date": entry_date, "Exit_Date": row["Date"],
                "Direction": "SHORT", "Entry_Price": entry_price,
                "Exit_Price": target2, "Qty": closed_qty,
                "PnL": pnl, "Capital": capital,
                "Exit_Reason": "TP2"
            })
        if remaining_qty <= 0:
            position = 0
            signal_state = 0

    # --- REVERSAL: Close position on opposite signal ---
    if position == 1 and bear:
        # Close remaining long
        pnl = (close - entry_price) * remaining_qty * LOT_SIZE
        capital += pnl
        trades.append({
            "Entry_Date": entry_date, "Exit_Date": row["Date"],
            "Direction": "LONG", "Entry_Price": entry_price,
            "Exit_Price": close, "Qty": remaining_qty,
            "PnL": pnl, "Capital": capital,
            "Exit_Reason": "REVERSAL"
        })
        position = 0
        # Set up pending short
        signal_state = -1
        sig_high = high
        sig_low = low
        sig_range = sig_high - sig_low

    elif position == -1 and bull:
        # Close remaining short
        pnl = (entry_price - close) * remaining_qty * LOT_SIZE
        capital += pnl
        trades.append({
            "Entry_Date": entry_date, "Exit_Date": row["Date"],
            "Direction": "SHORT", "Entry_Price": entry_price,
            "Exit_Price": close, "Qty": remaining_qty,
            "PnL": pnl, "Capital": capital,
            "Exit_Reason": "REVERSAL"
        })
        position = 0
        # Set up pending long
        signal_state = 1
        sig_high = high
        sig_low = low
        sig_range = sig_high - sig_low

    # --- SIGNAL REGISTRATION (only when flat) ---
    if position == 0:
        if signal_state == 0:
            if bull:
                signal_state = 1
                sig_high = high
                sig_low = low
                sig_range = sig_high - sig_low
            elif bear:
                signal_state = -1
                sig_high = high
                sig_low = low
                sig_range = sig_high - sig_low

        # Replace pending signal if opposite appears
        elif signal_state == 1 and bear:
            signal_state = -1
            sig_high = high
            sig_low = low
            sig_range = sig_high - sig_low

        elif signal_state == -1 and bull:
            signal_state = 1
            sig_high = high
            sig_low = low
            sig_range = sig_high - sig_low

        # --- CHECK STOP ENTRY FILL ---
        if signal_state == 1 and high >= sig_high:
            position = 1
            entry_price = sig_high
            entry_date = row["Date"]
            remaining_qty = ENTRY_QTY
            tp1_hit = False
            tp2_hit = False
            safe_range = sig_range if sig_range > 0 else 0.01
            target1 = entry_price + safe_range * 2
            target2 = entry_price + safe_range * 4
            signal_state = 0

        elif signal_state == -1 and low <= sig_low:
            position = -1
            entry_price = sig_low
            entry_date = row["Date"]
            remaining_qty = ENTRY_QTY
            tp1_hit = False
            tp2_hit = False
            safe_range = sig_range if sig_range > 0 else 0.01
            target1 = entry_price - safe_range * 2
            target2 = entry_price - safe_range * 4
            signal_state = 0

# --- Close any open position at end ---
if position != 0:
    last = df.iloc[-1]
    direction = "LONG" if position == 1 else "SHORT"
    pnl = (last["Close"] - entry_price) * remaining_qty * LOT_SIZE if position == 1 \
        else (entry_price - last["Close"]) * remaining_qty * LOT_SIZE
    capital += pnl
    trades.append({
        "Entry_Date": entry_date, "Exit_Date": last["Date"],
        "Direction": direction, "Entry_Price": entry_price,
        "Exit_Price": last["Close"], "Qty": remaining_qty,
        "PnL": pnl, "Capital": capital, "Exit_Reason": "END_OF_DATA"
    })

# === 6. RESULTS ===
trade_df = pd.DataFrame(trades)
print("=" * 70)
print("AISSR5sss STRATEGY RESULTS — NATURALGAS APR FUT")
print("=" * 70)

if trade_df.empty:
    print("No trades generated.")
else:
    total_pnl = trade_df['PnL'].sum()
    final_capital = trade_df['Capital'].iloc[-1]
    peak_capital = trade_df['Capital'].max()
    lowest_capital = trade_df['Capital'].min()
    max_drawdown = (trade_df['Capital'] - trade_df['Capital'].cummax()).min()
    roi = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    first_trade_date = trade_df['Entry_Date'].iloc[0]
    last_trade_date = trade_df['Exit_Date'].iloc[-1]
    trading_days = (last_trade_date - first_trade_date).days

    print(f"\nInitial Capital  : {INITIAL_CAPITAL:,.2f}")
    print(f"Final Capital    : {final_capital:,.2f}")
    print(f"Total PnL        : {total_pnl:,.2f}")
    print(f"ROI              : {roi:.2f}%")
    print(f"Trading Period   : {trading_days} days ({first_trade_date.strftime('%Y-%m-%d')} to {last_trade_date.strftime('%Y-%m-%d')})")
    print(f"Peak Capital     : {peak_capital:,.2f}")
    print(f"Lowest Capital   : {lowest_capital:,.2f} (drop: {INITIAL_CAPITAL - lowest_capital:,.2f})")
    print(f"Max Drawdown     : {max_drawdown:,.2f}")
    print(f"Total Trades     : {len(trade_df)}")
    print(f"Winning Trades   : {(trade_df['PnL'] > 0).sum()}")
    print(f"Losing Trades    : {(trade_df['PnL'] < 0).sum()}")
    print(f"Win Rate         : {(trade_df['PnL'] > 0).mean() * 100:.1f}%")
    print(f"Avg PnL/Trade    : {trade_df['PnL'].mean():.2f}")
    print(f"Max Profit       : {trade_df['PnL'].max():.2f}")
    print(f"Max Loss         : {trade_df['PnL'].min():.2f}")
    print(f"\n{'='*70}")
    print("TRADE LOG:")
    print("=" * 70)
    print(trade_df.to_string(index=False))

    # === 7. EXPORT TO CSV ===
    summary_df = pd.DataFrame({
        "Metric": [
            "Initial Capital", "Final Capital", "Total PnL", "ROI (%)",
            "Trading Period (days)", "Start Date", "End Date",
            "Peak Capital", "Lowest Capital", "Capital Drop",
            "Max Drawdown", "Total Trades", "Winning Trades",
            "Losing Trades", "Win Rate (%)", "Avg PnL/Trade",
            "Max Profit", "Max Loss"
        ],
        "Value": [
            f"{INITIAL_CAPITAL:,.2f}", f"{final_capital:,.2f}", f"{total_pnl:,.2f}", f"{roi:.2f}",
            trading_days, first_trade_date.strftime('%Y-%m-%d'), last_trade_date.strftime('%Y-%m-%d'),
            f"{peak_capital:,.2f}", f"{lowest_capital:,.2f}", f"{INITIAL_CAPITAL - lowest_capital:,.2f}",
            f"{max_drawdown:,.2f}", len(trade_df), (trade_df['PnL'] > 0).sum(),
            (trade_df['PnL'] < 0).sum(), f"{(trade_df['PnL'] > 0).mean() * 100:.1f}",
            f"{trade_df['PnL'].mean():.2f}", f"{trade_df['PnL'].max():.2f}", f"{trade_df['PnL'].min():.2f}"
        ]
    })

    summary_file = os.path.join(OUTPUT_DIR, "NG_backtest_summary.csv")
    trades_file = os.path.join(OUTPUT_DIR, "NG_backtest_trades.csv")
    summary_df.to_csv(summary_file, index=False)
    trade_df.to_csv(trades_file, index=False)
    print(f"\nSummary saved to {summary_file}")
    print(f"Trade log saved to {trades_file}")

