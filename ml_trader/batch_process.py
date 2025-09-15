# -*- coding: utf-8 -*-
"""
This helper script automates the process of loading multiple tick data CSV
files into the SQLite database.

It iterates through a predefined list of file paths and calls the
`process_ticks.py` script for each one.
"""
import subprocess
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def batch_process_files():
    """
    Processes a hardcoded list of CSV files using the process_ticks.py script.
    """
    # --- IMPORTANT ---
    # The user should replace these example paths with the actual, correct paths
    # to the CSV files on their local machine.
    # The 'r' before the string (e.g., r"C:\...") is important for Windows paths.
    file_paths = [
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_04_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_05_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_06_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_07_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_08_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_09_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_10_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_11_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_12_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_01_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_02_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_03_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_04_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_05_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_06_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_07_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2025_08_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_01_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_02_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_03_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_04_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_05_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_06_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_07_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_08_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_09_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_10_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_11_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2023_12_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_01_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_02_trades.csv",
        r"C:\Users\good day\Downloads\Back_test_Midcap\Futures\B\futures_BTCUSD_2024_03_trades.csv",
    ]

    logger.info(f"Found {len(file_paths)} files to process.")

    for path in file_paths:
        if not os.path.exists(path):
            logger.warning(f"File not found: {path}. Skipping.")
            continue

        logger.info(f"--- Processing file: {path} ---")
        try:
            # Construct the command to run the processing script
            # We assume 'python' is in the system's PATH
            command = ["python", "process_ticks.py", path]

            # Execute the command
            # We use subprocess.run for better control and error handling
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True  # This will raise an exception if the script returns a non-zero exit code
            )

            # Print the output from the script
            logger.info("Output from process_ticks.py:\n" + result.stdout)
            if result.stderr:
                logger.warning("Errors from process_ticks.py:\n" + result.stderr)

            logger.info(f"--- Finished processing: {path} ---")

        except FileNotFoundError:
             logger.error("Error: 'python' command not found. Please ensure Python is installed and in your system's PATH.")
             break
        except subprocess.CalledProcessError as e:
            logger.error(f"An error occurred while processing {path}.")
            logger.error("Exit Code: " + str(e.returncode))
            logger.error("Output:\n" + e.stdout)
            logger.error("Error Output:\n" + e.stderr)
            # Optional: decide if you want to stop on the first error
            # break
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            break

    logger.info("Batch processing complete.")


if __name__ == "__main__":
    batch_process_files()
