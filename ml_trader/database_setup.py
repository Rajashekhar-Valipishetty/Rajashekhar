# -*- coding: utf-8 -*-
"""
This script sets up the SQLite database and the necessary tables for storing
processed market data.
"""
import sqlite3
import logging

# --- Configuration ---
DB_PATH = 'ml_trader/market_data.db'

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_database():
    """
    Connects to the SQLite database and creates the ohlcv_data table
    if it doesn't already exist.
    """
    logger.info(f"Setting up database at: {DB_PATH}")

    try:
        # Connect to the database. This will create the file if it doesn't exist.
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # --- Create OHLCV Data Table ---
        # This table will store the candlestick data aggregated from ticks.
        create_table_query = """
        CREATE TABLE IF NOT EXISTS ohlcv_data (
            timestamp INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (timestamp, symbol, timeframe)
        );
        """

        logger.info("Executing CREATE TABLE statement for ohlcv_data...")
        cursor.execute(create_table_query)

        # Commit the changes and close the connection
        conn.commit()
        logger.info("Table 'ohlcv_data' created successfully or already exists.")

    except sqlite3.Error as e:
        logger.error(f"Database error occurred: {e}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")


if __name__ == '__main__':
    setup_database()
