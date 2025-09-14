# -*- coding: utf-8 -*-
"""
This script loads the processed OHLCV data from the SQLite database,
engineers features for trend and volatility, trains a KMeans clustering model
to identify market regimes, and saves the trained model and scaler.
"""
import sqlite3
import pandas as pd
import pandas_ta as ta
import logging
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# --- Configuration ---
DB_PATH = 'ml_trader/market_data.db'
MODEL_PATH = 'ml_trader/kmeans_model.pkl'
SCALER_PATH = 'ml_trader/scaler.pkl'
N_CLUSTERS = 4  # Number of market regimes to identify

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_data_from_db(symbol: str, timeframe: str) -> pd.DataFrame:
    """Loads OHLCV data from the SQLite database for a given symbol and timeframe."""
    logger.info(f"Loading data for {symbol} ({timeframe}) from {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT * FROM ohlcv_data WHERE symbol = '{symbol}' AND timeframe = '{timeframe}' ORDER BY timestamp ASC;"
        df = pd.read_sql_query(query, conn, parse_dates={'timestamp': 's'})
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
        df.set_index('timestamp', inplace=True)
        logger.info(f"Successfully loaded {len(df)} rows of data.")
        return df
    except Exception as e:
        logger.error(f"Failed to load data from database: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical indicators to be used as features for the model.
    This function is now robust to small amounts of data.
    """
    if df.empty:
        return df

    logger.info("Engineering features from OHLCV data...")

    # --- Volatility Features ---
    df.ta.atr(length=14, append=True)
    if 'ATR_14' in df.columns:
        df['atr_p'] = df['ATR_14'] / df['close'] * 100

    bbands = df.ta.bbands(length=20)
    if bbands is not None and all(col in bbands.columns for col in ['BBU_20_2.0', 'BBL_20_2.0', 'BBM_20_2.0']):
        df['bb_width_p'] = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0'] * 100

    # --- Trend/Momentum Features ---
    df.ta.rsi(length=14, append=True)

    macd = df.ta.macd(fast=12, slow=26)
    if macd is not None and 'MACDh_12_26_9' in macd.columns:
        df['macd_hist'] = macd['MACDh_12_26_9']

    # Check for sufficient data before calculating slope
    if len(df) > 5:
        df['ema_5_slope'] = df.ta.ema(length=5).diff()

    # Drop rows with NaN values created by the indicators
    df.dropna(inplace=True)

    logger.info("Feature engineering complete.")
    return df


def train_model(df: pd.DataFrame):
    """Trains a KMeans model and saves it along with the scaler."""
    feature_columns = ['atr_p', 'bb_width_p', 'RSI_14', 'macd_hist', 'ema_5_slope']

    # Filter for columns that actually exist in the dataframe
    existing_features = [col for col in feature_columns if col in df.columns]

    if not existing_features:
        logger.error("No features were generated, likely due to insufficient data. Cannot train model.")
        return

    features_df = df[existing_features]

    if features_df.empty:
        logger.error("DataFrame is empty after feature selection. Cannot train model.")
        return

    logger.info(f"Training model on {len(features_df)} data points with features: {existing_features}")

    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features_df)

    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    kmeans.fit(scaled_features)

    df['regime'] = kmeans.labels_

    logger.info("Model training complete. Market regime counts:")
    logger.info(df['regime'].value_counts().sort_index())

    logger.info(f"Saving scaler to {SCALER_PATH}")
    joblib.dump(scaler, SCALER_PATH)

    logger.info(f"Saving KMeans model to {MODEL_PATH}")
    joblib.dump(kmeans, MODEL_PATH)

    logger.info("Model and scaler saved successfully.")


if __name__ == '__main__':
    ohlcv_data = load_data_from_db(symbol='BTCUSD', timeframe='1h')

    if not ohlcv_data.empty:
        featured_data = engineer_features(ohlcv_data)
        train_model(featured_data)
    else:
        logger.error("No data available to train the model. Please run process_ticks.py first.")
