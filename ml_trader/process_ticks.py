# -*- coding: utf-8 -*-
"""
This script processes a CSV file of tick-by-tick trade data, aggregates it
into OHLCV (candlestick) format for a specified timeframe, and loads it
into the SQLite database.

This version is updated to handle the user-provided CSV format:
product_symbol,price,size,timestamp,buyer_role
"""
import pandas as pd
import sqlite3
import logging
import argparse

# --- Configuration ---
DB_PATH = 'ml_trader/market_data.db'

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_tick_data_to_ohlcv(csv_path: str, timeframe: str = '1H') -> (pd.DataFrame, str):
    """
    Reads tick data from a CSV and resamples it into OHLCV format.

    Args:
        csv_path (str): The full path to the input CSV file.
        timeframe (str): The timeframe for resampling (e.g., '1T' for 1 min,
                         '1H' for 1 hour, '1D' for 1 day).

    Returns:
        A tuple containing:
        - pd.DataFrame: A DataFrame with the aggregated OHLCV data.
        - str: The symbol found in the CSV file.
    """
    logger.info(f"Reading tick data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)

        # --- Data Validation and Preparation ---
        required_columns = ['timestamp', 'price', 'size', 'product_symbol']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"CSV must contain the columns: {required_columns}")

        # Extract the symbol. Assume it's the same for the whole file.
        symbol = df['product_symbol'].iloc[0]
        logger.info(f"Detected symbol: {symbol}")

        # Convert string timestamp to datetime objects. Using `to_datetime` without a specific
        # format string is often robust enough if the format is standard.
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df.set_index('timestamp', inplace=True)

        logger.info(f"Resampling data to {timeframe} timeframe...")

        ohlc_logic = {
            'price': ['first', 'max', 'min', 'last'],
            'size': 'sum'
        }

        # Resample the data. Using 'h' for hour as 'H' is deprecated.
        resample_tf = timeframe.replace('H', 'h').replace('T','min')
        ohlcv_df = df.resample(resample_tf).apply(ohlc_logic)
        ohlcv_df.columns = ['open', 'high', 'low', 'close', 'volume']
        ohlcv_df.dropna(inplace=True)

        logger.info(f"Successfully created {len(ohlcv_df)} OHLCV candles for {symbol}.")
        return ohlcv_df, symbol

    except FileNotFoundError:
        logger.error(f"Error: The file was not found at {csv_path}")
        return pd.DataFrame(), None
    except Exception as e:
        logger.error(f"An error occurred during data processing: {e}")
        return pd.DataFrame(), None


def load_ohlcv_to_db(ohlcv_df: pd.DataFrame, symbol: str, timeframe_str: str):
    """
    Loads a DataFrame of OHLCV data into the SQLite database.
    """
    if ohlcv_df.empty:
        logger.warning("OHLCV DataFrame is empty. Nothing to load into the database.")
        return

    logger.info(f"Connecting to database at {DB_PATH} to load data for {symbol}.")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        data_to_insert = ohlcv_df.reset_index()
        data_to_insert['timestamp'] = data_to_insert['timestamp'].apply(lambda x: int(x.timestamp()))
        data_to_insert['symbol'] = symbol
        data_to_insert['timeframe'] = timeframe_str

        data_to_insert = data_to_insert[['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume']]

        insert_query = """
        INSERT OR IGNORE INTO ohlcv_data (timestamp, symbol, timeframe, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """

        logger.info(f"Inserting {len(data_to_insert)} rows into the database...")
        cursor.executemany(insert_query, data_to_insert.to_records(index=False))

        conn.commit()
        logger.info("Data loaded into 'ohlcv_data' table successfully.")

    except sqlite3.Error as e:
        logger.error(f"Database error occurred during data loading: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process tick data CSV into OHLCV candles and load into a database.")
    parser.add_argument("csv_path", type=str, help="Path to the input tick data CSV file.")
    parser.add_argument("--timeframe", type=str, default="1H", help="The timeframe to resample to (e.g., '1T', '15min', '1h', '1D').")

    args = parser.parse_args()

    # 1. Process the CSV to get OHLCV data and the symbol
    ohlcv_data, symbol_found = process_tick_data_to_ohlcv(args.csv_path, args.timeframe)

    # 2. Load the processed data into the database if processing was successful
    if symbol_found:
        load_ohlcv_to_db(ohlcv_data, symbol_found, args.timeframe)
