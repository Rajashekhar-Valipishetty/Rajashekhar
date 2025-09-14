# AI-Powered Adaptive Grid Trading Bot for Delta Exchange

This project is a sophisticated, AI-powered grid trading bot designed to trade perpetual futures on Delta Exchange. It features a full data processing pipeline to train a custom machine learning model on user-provided tick data, and a simple web-based user interface for control and monitoring.

---

## Key Features

- **AI-Driven Strategy:** Uses a K-Means clustering model to analyze market conditions and classify them into distinct "regimes" (e.g., low volatility, high volatility, trending).
- **Adaptive Trading:** Dynamically adjusts grid trading parameters (like grid spacing and the number of orders) in real-time based on the AI-predicted market regime.
- **Local Data Training:** Includes a complete data pipeline to process your own tick-by-tick trade data from CSV files, ensuring the AI model is perfectly tailored to your data source.
- **Web-Based UI:** A simple and intuitive web control panel allows you to start, stop, and monitor the bot without touching the code.
- **Robust & Modular:** The code is organized into logical components for the bot, the data processing pipeline, and the frontend, making it easy to understand and maintain.

---

## How to Use

Follow these steps carefully to get the bot running on your local machine.

### Step 1: Setup and Installation

1.  **Get the Code:** First, make sure you have all the project files on your computer, organized in the following folder structure:
    ```
    ml_trader/
    ├── bot/
    │   ├── delta_grid_bot.py
    │   └── .env.example
    ├── frontend/
    │   ├── app.py
    │   └── templates/
    │       └── index.html
    ├── database_setup.py
    ├── process_ticks.py
    ├── train_model.py
    └── requirements.txt
    ```

2.  **Install Dependencies:** Open a terminal or command prompt, navigate to the main `ml_trader` folder, and run the following command to install the necessary software libraries:
    ```bash
    pip install -r requirements.txt
    ```

### Step 2: Add Your API Keys

1.  Navigate into the `ml_trader/bot/` folder.
2.  Make a copy of the `.env.example` file and rename the copy to **`.env`**.
3.  Open the new `.env` file with a text editor and replace the placeholders with your actual Delta Exchange **Testnet** API key and secret.
    ```ini
    DELTA_API_KEY="your_real_api_key_goes_here"
    DELTA_API_SECRET="your_real_api_secret_goes_here"
    ```
4.  Save and close the file. **Do not share this file or your keys with anyone.**

### Step 3: Process Your Tick Data

This step converts your raw CSV trade data into a format the AI can learn from.

1.  Place your tick data CSV file(s) somewhere on your computer. Make sure they have the format: `product_symbol,price,size,timestamp,buyer_role`.
2.  In your terminal, from the main `ml_trader` directory, run the following command for **each** CSV file you want to process. Replace `/path/to/your/file.csv` with the actual path to your file.
    ```bash
    python process_ticks.py /path/to/your/file.csv
    ```
    This will create and populate a `market_data.db` file in your project folder.

### Step 4: Train the AI Model

After you have processed all your data, you need to train the AI model.

1.  In your terminal, from the main `ml_trader` directory, run this command:
    ```bash
    python train_model.py
    ```
2.  This will use the data in `market_data.db` to train the model and will create two new files in your project folder: `kmeans_model.pkl` and `scaler.pkl`. The bot needs these files to make its predictions.

### Step 5: Run the Bot and Web UI

Now you are ready to launch the bot!

1.  In your terminal, from the main `ml_trader` directory, run the web application:
    ```bash
    python frontend/app.py
    ```
2.  You will see log messages indicating the server has started.
3.  Open your web browser (e.g., Chrome, Firefox) and go to the following address:
    ```
    http://127.0.0.1:5000
    ```
4.  You will see the control panel. From here, you can configure the initial parameters and click **"Start Bot"**. The status panel will update to show you what the bot and its AI are doing.

---

## Disclaimer

Trading cryptocurrencies carries a high level of risk and may not be suitable for all investors. This software is provided "as is" for educational and experimental purposes only. The author is not responsible for any financial losses you may incur. Use at your own risk and never trade with money you cannot afford to lose.
