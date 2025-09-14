# -*- coding: utf-8 -*-
"""
This script creates a Flask web application to control and monitor the
DeltaGridBot.
"""
import sys
import os
import threading
import logging
from flask import Flask, render_template, request, jsonify

# Add the parent directory to the Python path to allow sibling imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bot.delta_grid_bot import DeltaGridBot

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Global State Management ---
# This is a simple way to manage the bot's state. For a production system,
# a more robust solution like a database or a proper state manager would be better.
bot_thread = None
bot_instance: DeltaGridBot = None
bot_status = {
    "status": "Stopped",
    "symbol": None,
    "regime": "N/A",
    "grid_spacing": "N/A",
    "grid_count": "N/A",
    "start_time": None
}

# --- Bot Runner Function ---
def run_bot_thread(config):
    """Function to be executed in a separate thread."""
    global bot_instance, bot_status
    try:
        bot_instance = DeltaGridBot(
            symbol=config['symbol'],
            investment_per_grid=config['investment_per_grid'],
            # The number_of_grids and grid_spacing_percent are now controlled
            # entirely by the bot's internal adaptive strategy.
            global_stop_loss_percent=config['global_stop_loss_percent']
        )
        # Update status
        bot_status['symbol'] = bot_instance.symbol
        bot_status['status'] = "Running"

        # This is a blocking call, it will run until the bot stops or crashes
        bot_instance.run()

    except Exception as e:
        app.logger.error(f"Bot thread encountered a critical error: {e}", exc_info=True)
        bot_status['status'] = f"Error: {e}"
    finally:
        bot_status['status'] = "Stopped"
        app.logger.info("Bot thread has finished execution.")


# --- Flask Routes ---
@app.route('/')
def index():
    """Renders the main control panel UI."""
    # We will create this template in the next step.
    return render_template('index.html')


@app.route('/start', methods=['POST'])
def start_bot():
    """Starts the trading bot in a background thread."""
    global bot_thread, bot_status

    if bot_thread and bot_thread.is_alive():
        return jsonify({"status": "error", "message": "Bot is already running."}), 400

    try:
        # Extract parameters from the form submission
        config = {
            "symbol": request.form.get('symbol', 'BTCUSDT'),
            "investment_per_grid": float(request.form.get('investment_per_grid', 100.0)),
            "global_stop_loss_percent": float(request.form.get('global_stop_loss_percent', 5.0))
        }
        app.logger.info(f"Received start request with config: {config}")

        # Start the bot in a new thread
        bot_thread = threading.Thread(target=run_bot_thread, args=(config,))
        bot_thread.daemon = True # Allows main thread to exit even if bot thread is running
        bot_thread.start()

        app.logger.info("Bot thread started.")
        return jsonify({"status": "success", "message": "Bot started successfully."})

    except Exception as e:
        app.logger.error(f"Failed to start bot: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Failed to start bot: {e}"}), 500


@app.route('/stop', methods=['POST'])
def stop_bot():
    """Stops the trading bot gracefully."""
    global bot_thread, bot_instance, bot_status

    if not bot_thread or not bot_thread.is_alive() or not bot_instance:
        return jsonify({"status": "error", "message": "Bot is not running."}), 400

    app.logger.info("Received request to stop the bot.")

    try:
        # Signal the bot thread to stop
        bot_instance.stop()
        # Wait for the thread to finish
        bot_thread.join(timeout=10) # Add a timeout for safety

        if bot_thread.is_alive():
             app.logger.warning("Bot thread did not terminate in time.")
             # Fallback to just cancelling orders if join fails
             bot_instance.cancel_all_orders()
             message = "Bot thread is not responding. All orders cancelled, but thread may still be running."
        else:
             app.logger.info("Bot thread terminated gracefully.")
             message = "Bot stopped successfully."

        # Reset global state
        bot_thread = None
        bot_instance = None
        bot_status['status'] = "Stopped"

        return jsonify({"status": "success", "message": message})
    except Exception as e:
        app.logger.error(f"An error occurred while stopping the bot: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"An error occurred: {e}"}), 500


@app.route('/status')
def status():
    """Returns the current status of the bot."""
    global bot_status, bot_instance

    if bot_instance and bot_thread.is_alive():
        # If the bot is running, get live data from the instance
        return jsonify({
            "status": "Running",
            "symbol": bot_instance.symbol,
            "regime": bot_instance.current_regime_name,
            "grid_spacing": f"{bot_instance.grid_spacing * 100:.2f}%",
            "grid_count": bot_instance.number_of_grids
        })
    else:
        # Return the last known status if the bot is stopped or has crashed
        return jsonify(bot_status)


if __name__ == '__main__':
    # It's not recommended to run in debug mode in production
    # Use a proper WSGI server like Gunicorn or Waitress
    app.run(host='0.0.0.0', port=5000, debug=True)
