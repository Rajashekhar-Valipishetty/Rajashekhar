# -*- coding: utf-8 -*-
"""
This script implements a grid trading bot for Delta Exchange.

Disclaimer:
Trading cryptocurrencies carries a high level of risk, and may not be suitable
for all investors. Before deciding to trade cryptocurrency you should carefully
consider your investment objectives, level of experience, and risk appetite.
The possibility exists that you could sustain a loss of some or all of your
initial investment and therefore you should not invest money that you cannot
afford to lose. You should be aware of all the risks associated with
cryptocurrency trading, and seek advice from an independent financial advisor
if you have any doubts.

This is not financial advice. Use this script at your own risk.
The author is not responsible for any losses you may incur.
"""
import os
import time
import logging
import hmac
import hashlib
import json
import threading
from typing import Dict, Any, List, Optional
import ccxt
import pandas as pd
import pandas_ta as ta

import requests
from dotenv import load_dotenv

# --- Basic Configuration ---
# Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class DeltaGridBot:
    """
    A grid trading bot for Delta Exchange that automates placing buy and sell
    orders within a predefined price grid.
    """
    # Using Testnet URL. For production, use https://api.delta.exchange
    BASE_URL = "https://testnet-api.delta.exchange"

    def __init__(self,
                 symbol: str,
                 investment_per_grid: float,
                 number_of_grids: int,
                 grid_spacing_percent: float,
                 global_stop_loss_percent: float):
        """
        Initializes the DeltaGridBot.

        Args:
            symbol (str): The trading symbol (e.g., 'BTCUSDT').
            investment_per_grid (float): The amount of quote currency (e.g., USDT)
                                         to use for each grid level order.
            number_of_grids (int): The total number of grid lines. Must be an even number.
            grid_spacing_percent (float): The spacing between grid levels as a
                                          percentage (e.g., 0.5 for 0.5%).
            global_stop_loss_percent (float): The percentage drop from the initial
                                              price at which to stop the bot.
        """
        # --- API Credentials ---
        self.api_key = os.getenv("DELTA_API_KEY")
        self.api_secret = os.getenv("DELTA_API_SECRET")
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret must be set in the .env file.")

        # --- Strategy Parameters ---
        self.symbol = symbol
        self.investment_per_grid = investment_per_grid
        if number_of_grids % 2 != 0:
            raise ValueError("number_of_grids must be an even number.")
        self.number_of_grids = number_of_grids
        self.grid_spacing = grid_spacing_percent / 100.0  # Convert to decimal
        self.global_stop_loss = global_stop_loss_percent / 100.0

        # --- Internal State ---
        self.session = requests.Session()
        self.product_id: Optional[int] = None
        self.initial_price: Optional[float] = None
        self.stop_loss_price: Optional[float] = None
        self.processed_fill_ids = set()
        self.active_grid_orders = {} # To track our placed orders {order_id: order_info}

        # --- Adaptive Strategy Parameters ---
        self.strategy_config = {
            'LOW': {'spacing': 0.3, 'grids': 20},   # Tighter grid in low volatility
            'MEDIUM': {'spacing': 0.8, 'grids': 10}, # Default balanced grid
            'HIGH': {'spacing': 1.5, 'grids': 6}    # Wider grid in high volatility
        }
        self.current_volatility_regime = 'MEDIUM' # Start with a neutral assumption
        # Set initial grid params from the default medium strategy
        self.grid_spacing = self.strategy_config[self.current_volatility_regime]['spacing'] / 100.0
        self.number_of_grids = self.strategy_config[self.current_volatility_regime]['grids']

        # --- Threading Control ---
        self.stop_event = threading.Event()

    def stop(self):
        """Signals the bot to stop its execution loop."""
        logger.info("Stop signal received. The bot will exit after the current loop.")
        self.stop_event.set()

    def _api_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        A helper method to handle all authenticated API requests.

        Args:
            method (str): HTTP method (GET, POST, DELETE).
            endpoint (str): API endpoint path (e.g., '/orders').
            data (dict, optional): Request payload for POST requests.

        Returns:
            dict: The JSON response from the API.

        Raises:
            requests.exceptions.RequestException: For network or HTTP errors.
        """
        timestamp = str(int(time.time()))
        path = f"/api/v2{endpoint}"
        body = json.dumps(data) if data else ''

        # Create the signature
        signature_string = timestamp + method.upper() + path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            'api-key': self.api_key,
            'timestamp': timestamp,
            'signature': signature,
            'Content-Type': 'application/json'
        }

        url = self.BASE_URL + path
        try:
            response = self.session.request(method, url, headers=headers, data=body.encode('utf-8'))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request to {url} failed: {e}")
            if e.response:
                logger.error(f"Response content: {e.response.text}")
            raise

    def _get_product_id(self) -> int:
        """Fetches the product ID for the given symbol."""
        logger.info(f"Fetching product ID for symbol: {self.symbol}")
        products = self._api_request('GET', '/products')
        for product in products['result']:
            if product['symbol'] == self.symbol:
                logger.info(f"Found product ID: {product['id']} for {self.symbol}")
                return product['id']
        raise ValueError(f"Product ID for symbol '{self.symbol}' not found.")

    def get_mark_price(self) -> float:
        """Fetches the current mark price for the product."""
        if not self.product_id:
            raise ValueError("Product ID not set. Cannot fetch mark price.")

        product_details = self._api_request('GET', f'/products/{self.product_id}')
        mark_price = float(product_details['result']['mark_price'])
        logger.debug(f"Current mark price for {self.symbol}: {mark_price}")
        return mark_price

    def _fetch_recent_candles(self, timeframe: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetches the most recent N candles using ccxt to be used in TA calculations.
        """
        logger.info(f"Attempting to fetch last {limit} candles for {self.symbol} using ccxt.")
        try:
            exchange = ccxt.delta({'options': {'adjustForTimeDifference': True}})
            exchange.set_sandbox_mode(True)
            exchange.load_markets()

            if self.symbol == 'BTCUSDT':
                ccxt_symbol = 'BTC/USDT:USDT'
            elif self.symbol == 'ETHUSDT':
                ccxt_symbol = 'ETH/USDT:USDT'
            else:
                ccxt_symbol = self.symbol.replace('USDT', '/USDT:USDT')

            if not exchange.has['fetchOHLCV']:
                logger.warning("CCXT reports that Delta exchange does not support fetchOHLCV.")
                return None

            ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)

            if not ohlcv:
                logger.warning("No candle data returned from ccxt for Delta testnet.")
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('time', inplace=True)
            df.drop('timestamp', axis=1, inplace=True)

            logger.info(f"Successfully fetched {len(df)} recent candles via ccxt.")
            return df

        except Exception as e:
            logger.error(f"Could not fetch recent candles via ccxt due to an error: {e}")
            return None

    def update_grid_parameters(self) -> bool:
        """
        Analyzes market volatility using Bollinger Bands and updates grid
        parameters if the regime changes.

        Returns:
            bool: True if the grid parameters were changed, False otherwise.
        """
        logger.info("Analyzing market volatility to adapt grid strategy...")
        candles_df = self._fetch_recent_candles(limit=100)

        if candles_df is None or candles_df.empty:
            logger.warning("Could not fetch candle data for analysis. Sticking to current parameters.")
            return False

        # Calculate Bollinger Bands
        # Using standard parameters (20-period, 2 standard deviations)
        candles_df.ta.bbands(length=20, append=True)

        # Calculate Bollinger Band Width Percentage
        candles_df['bb_width_p'] = (candles_df['BBU_20_2.0'] - candles_df['BBL_20_2.0']) / candles_df['BBM_20_2.0']

        # Get the latest band width value
        latest_bbwp = candles_df['bb_width_p'].iloc[-1]

        new_regime = None
        # Define thresholds for volatility regimes (these are examples and can be tuned)
        if latest_bbwp < 0.03: # Example: 3% width = low volatility
            new_regime = 'LOW'
        elif latest_bbwp > 0.08: # Example: 8% width = high volatility
            new_regime = 'HIGH'
        else:
            new_regime = 'MEDIUM'

        logger.info(f"Latest BBW%: {latest_bbwp:.4f}. Detected regime: {new_regime}")

        if new_regime != self.current_volatility_regime:
            logger.warning(f"Volatility regime change detected! From {self.current_volatility_regime} to {new_regime}.")
            self.current_volatility_regime = new_regime

            # Update parameters from the strategy config
            new_params = self.strategy_config[new_regime]
            self.grid_spacing = new_params['spacing'] / 100.0
            self.number_of_grids = new_params['grids']

            logger.warning(f"New grid parameters: Spacing={new_params['spacing']}%, Grids={new_params['grids']}")
            return True # Signal that parameters have changed

        logger.info(f"Volatility regime stable at {self.current_volatility_regime}. No changes to grid.")
        return False

    def cancel_all_orders(self) -> None:
        """Cancels all existing open orders for the product."""
        if not self.product_id:
            raise ValueError("Product ID not set. Cannot cancel orders.")

        logger.info(f"Cancelling all open orders for product ID: {self.product_id}")
        payload = {'product_id': self.product_id}
        response = self._api_request('DELETE', '/orders/all', data=payload)
        logger.info(f"Cancelled orders response: {response.get('message', 'Success')}")
        self.active_grid_orders.clear()

    def place_order(self, side: str, price: float, size: float) -> Optional[Dict]:
        """
        Places a single limit order.

        Args:
            side (str): 'buy' or 'sell'.
            price (float): The price for the limit order.
            size (float): The quantity to buy or sell.

        Returns:
            dict or None: The created order details if successful, else None.
        """
        if not self.product_id:
            raise ValueError("Product ID not set. Cannot place order.")

        # Delta API requires size to be an integer (number of contracts)
        order_size = int(size)
        if order_size == 0:
            logger.warning(f"Order size is 0 for price {price}. Skipping.")
            return None

        payload = {
            "product_id": self.product_id,
            "order_type": "limit_order",
            "size": order_size,
            "side": side,
            "limit_price": str(price) # API expects price as a string
        }
        try:
            logger.info(f"Placing {side} order: {order_size} contracts of {self.symbol} @ {price}")
            created_order = self._api_request('POST', '/orders', data=payload)
            logger.info(f"Successfully placed {side} order ID: {created_order['result']['id']}")
            return created_order['result']
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to place {side} order at {price}: {e}")
            return None

    def place_initial_grid(self, current_price: float) -> None:
        """Calculates and places the initial set of grid orders."""
        logger.info("Placing initial grid of orders...")
        half_grids = self.number_of_grids // 2

        # --- Place Buy Orders Below Current Price ---
        for i in range(1, half_grids + 1):
            buy_price = round(current_price * (1 - i * self.grid_spacing), 4)
            order_size = self.investment_per_grid / buy_price
            order = self.place_order('buy', buy_price, order_size)
            if order:
                self.active_grid_orders[order['id']] = order

        # --- Place Sell Orders Above Current Price ---
        for i in range(1, half_grids + 1):
            sell_price = round(current_price * (1 + i * self.grid_spacing), 4)
            order_size = self.investment_per_grid / sell_price
            order = self.place_order('sell', sell_price, order_size)
            if order:
                self.active_grid_orders[order['id']] = order

        logger.info(f"Initial grid placed. Total active orders: {len(self.active_grid_orders)}")

    def check_fills_and_rebalance(self) -> None:
        """Checks for filled orders and places corresponding take-profit orders."""
        if not self.product_id:
            return

        logger.debug("Checking for order fills...")
        try:
            # Fetch all filled orders for the product
            fills = self._api_request('GET', f"/orders/fills?product_id={self.product_id}")

            for fill in fills['result']:
                if fill['id'] in self.processed_fill_ids:
                    continue # Skip already processed fills

                fill_price = float(fill['filled_price'])
                fill_size = int(fill['filled_size'])

                logger.info(f"New fill detected! Order ID: {fill['order_id']}, Side: {fill['side']}, "
                            f"Size: {fill_size} @ {fill_price}")

                if fill['side'] == 'buy':
                    # A buy order was filled, place a sell order one grid level higher
                    take_profit_price = round(fill_price * (1 + self.grid_spacing), 4)
                    self.place_order('sell', take_profit_price, fill_size)

                elif fill['side'] == 'sell':
                    # A sell order was filled, place a buy order one grid level lower
                    take_profit_price = round(fill_price * (1 - self.grid_spacing), 4)
                    self.place_order('buy', take_profit_price, fill_size)

                # Mark this fill as processed to avoid duplicate actions
                self.processed_fill_ids.add(fill['id'])

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check fills: {e}")

    def run(self, loop_interval_sec: int = 15):
        """The main event loop for the trading bot."""
        logger.info("--- Starting Delta Grid Bot ---")
        try:
            self.product_id = self._get_product_id()

            # --- Initial Setup ---
            logger.info("Performing initial setup...")
            self.cancel_all_orders()
            time.sleep(2) # Give a moment for orders to be confirmed as cancelled

            self.initial_price = self.get_mark_price()
            logger.info(f"Initial mark price for {self.symbol} is {self.initial_price}")

            # Set the global stop loss price
            self.stop_loss_price = self.initial_price * (1 - self.global_stop_loss)
            logger.info(f"Global stop-loss triggered if price falls below: {self.stop_loss_price:.4f}")

            self.place_initial_grid(self.initial_price)

            # --- Main Event Loop ---
            logger.info("\n--- Entering main event loop ---\n")
            loop_counter = 0
            while not self.stop_event.is_set():
                # --- Adaptive Strategy Check (every 15 loops) ---
                if loop_counter % 15 == 0:
                    if self.update_grid_parameters():
                        logger.info("Regime change detected, resetting grid.")
                        self.cancel_all_orders()
                        time.sleep(2) # Pause for safety
                        current_price = self.get_mark_price()
                        self.place_initial_grid(current_price)
                        logger.info("Grid has been reset with new parameters.")

                current_price = self.get_mark_price()

                # 1. Global Stop-Loss Check
                if current_price <= self.stop_loss_price:
                    logger.warning("!!! GLOBAL STOP-LOSS TRIGGERED !!!")
                    logger.warning(f"Current price {current_price} is below stop-loss price {self.stop_loss_price}")
                    self.cancel_all_orders()
                    logger.info("All orders cancelled. Exiting bot.")
                    break

                # 2. Check for fills and create new orders
                self.check_fills_and_rebalance()

                logger.debug(f"Loop finished. Waiting for {loop_interval_sec} seconds...")
                loop_counter += 1
                time.sleep(loop_interval_sec)

        except (ValueError, requests.exceptions.RequestException) as e:
            logger.critical(f"A critical error occurred: {e}")
            logger.critical("Bot is shutting down.")
        except KeyboardInterrupt:
            logger.info("Shutdown signal received. Cleaning up...")
            self.cancel_all_orders()
            logger.info("Cleanup complete. Bot has been stopped.")


if __name__ == '__main__':
    """
    Main entry point to run the bot.
    Configure your strategy parameters here.
    """
    logger.info("Initializing bot from main execution block.")

    # --- STRATEGY CONFIGURATION ---
    # It's recommended to use a high-volume, liquid perpetual contract.
    # For testnet, 'BTCUSDT' or 'ETHUSDT' are good choices.
    SYMBOL = 'BTCUSDT'

    # Investment amount in quote currency (e.g., USDT) for each grid line.
    # If a buy order at $60,000 is placed, the size will be 100/60000 contracts.
    INVESTMENT_PER_GRID_LINE = 100.0  # in USDT

    # Total number of buy and sell orders to maintain. This is now controlled by the adaptive strategy.
    # The distance between grid lines as a percentage of the price. This is now controlled by the adaptive strategy.

    # If the price drops by this percentage from the start, cancel all orders and stop.
    GLOBAL_STOP_LOSS_PERCENT = 5.0 # 5%

    try:
        # This part will only run if a .env file with API keys is present.
        # number_of_grids and grid_spacing_percent are now managed internally by the bot.
        bot = DeltaGridBot(
            symbol=SYMBOL,
            investment_per_grid=INVESTMENT_PER_GRID_LINE,
            global_stop_loss_percent=GLOBAL_STOP_LOSS_PERCENT
        )
        bot.run()
    except Exception as e:
        logger.critical(f"Failed to initialize or run the bot: {e}", exc_info=True)
