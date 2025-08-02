# Streamlit Odds Analysis Dashboard

## Setup

1. Make sure you have installed all dependencies:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Ensure your database is set up and contains games and odds data.

3. Make sure your `.env` file contains the `DATABASE_URL` connection string.

## Running the Dashboard

Start the Streamlit app:

```bash
source venv/bin/activate
streamlit run streamlit_app.py
```

The dashboard will open in your browser, typically at `http://localhost:8501`.

## Features

- **Game Selection**: Dropdown to select any game from the database
- **Odds Table**: Sortable table showing all odds data with filters for:
  - Platform (Polymarket, Kalshi, sportsbooks, etc.)
  - Outcome type (home_win, away_win, etc.)
  - Closing lines only
- **Time Series Chart**: Interactive scatterplot showing odds over time with:
  - Multiple outcome types
  - Different platforms represented by symbols
  - Raw vs de-vigged odds options
  - Game start time marker
- **Summary Statistics**: Min, max, mean, standard deviation, and count by platform and outcome

## Data Display

The table includes:
- Timestamp of odds collection
- Platform name and type
- Outcome type and decimal odds
- Raw and de-vigged probabilities
- Closing line indicator

The chart visualizes how odds change over time leading up to the game start, helping identify which platforms have the most stable or accurate predictions.