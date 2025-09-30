# This script is for the initial, one-time population of your database.
# It fetches several years of historical data for all NSE stocks.
# WARNING: This will take several hours to run.

import pymongo
# This is the correct, modern import statement for the library.
from Smartapi import SmartConnect
import pandas as pd
import time
from datetime import datetime

# --- IMPORTANT: FILL IN YOUR CREDENTIALS HERE ---
MONGO_CONNECTION_STRING = "YOUR_MONGO_CONNECTION_STRING_HERE"
API_KEY = "YOUR_ANGEL_ONE_API_KEY"
USER_ID = "YOUR_ANGEL_ONE_USER_ID"
PASSWORD = "YOUR_ANGEL_ONE_PASSWORD"
TOTP = "YOUR_ANGEL_ONE_TOTP_SECRET"
# --- END OF CREDENTIALS ---


# --- 1. DATABASE CONNECTION ---
print("Connecting to MongoDB...")
client = pymongo.MongoClient(MONGO_CONNECTION_STRING)
db = client['stock_market_data']
collection = db['daily_stock_data']
print("✅ Successfully connected to MongoDB.")


# --- 2. AUTHENTICATE WITH ANGEL ONE ---
print("Connecting to Angel One SmartAPI...")
smartApi = SmartConnect(API_KEY)
session_data = smartApi.generateSession(USER_ID, PASSWORD, TOTP)
print("✅ Angel One session created.")


# --- 3. GET THE MASTER LIST OF INSTRUMENTS ---
print("Fetching master instrument list...")
instrument_url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
instrument_df = pd.read_json(instrument_url)
# Filter for only NSE equity stocks that are currently traded
nse_stocks = instrument_df[
    (instrument_df['exch_seg'] == 'NSE') & 
    (instrument_df['instrumenttype'] == 'EQUITY') &
    (instrument_df['symbol'].str.contains('-EQ'))
]
print(f"✅ Found {len(nse_stocks)} NSE equity stocks to process.")


# --- 4. LOOP AND FETCH HISTORICAL DATA ---
print("\nStarting bulk data import. This will take a long time...")
for index, stock in nse_stocks.iterrows():
    instrument_token = stock['token']
    instrument_symbol = stock['symbol']
    
    print(f"Fetching data for: {instrument_symbol} (Token: {instrument_token})")

    try:
        # Define parameters for historical data (e.g., from 2022 to today)
        hist_params = {
            "exchange": "NSE",
            "symboltoken": instrument_token,
            "interval": "ONE_DAY",
            "fromdate": "2022-01-01 09:15",
            "todate": datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        
        api_response = smartApi.getCandleData(hist_params)

        if api_response['status'] and api_response['data']:
            records_to_insert = []
            for candle in api_response['data']:
                # The API returns data as a list: [timestamp, open, high, low, close, volume]
                record = {
                    "_id": f"{instrument_token}_{candle[0].split('T')[0]}", # Unique ID: token + date
                    "instrument_token": instrument_token,
                    "symbol": instrument_symbol,
                    "date": datetime.fromisoformat(candle[0]), # Convert to proper datetime object
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5]
                }
                records_to_insert.append(record)
            
            # Insert the data into MongoDB
            if records_to_insert:
                collection.insert_many(records_to_insert)
                print(f"   -> Inserted {len(records_to_insert)} records for {instrument_symbol}.")
        else:
            print(f"   -> No data returned for {instrument_symbol}.")

    except Exception as e:
        print(f"   -> ERROR fetching or inserting for {instrument_symbol}: {e}")

    # Respect API Rate Limits
    time.sleep(0.4) # Wait 0.4 seconds between each stock

print("\n🚀 Bulk data import complete!")

