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

### Game Analysis Page
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

### Brier Scores Page
- **Platform Performance**: Comprehensive table showing Brier scores for each platform
- **Performance Metrics**: Number of games, predictions, accuracy, and average predicted probabilities
- **Interactive Filters**: Filter by platform type and minimum number of predictions
- **Visual Comparison**: Bar chart comparing Brier scores across platforms
- **Key Insights**: Highlights of best performers and most active platforms

## Data Display

### Game Analysis Data
The odds table includes:
- Timestamp of odds collection
- Platform name and type
- Outcome type and decimal odds
- Raw and de-vigged probabilities
- Closing line indicator

The time series chart visualizes how odds change over time leading up to the game start, helping identify which platforms have the most stable or accurate predictions.

### Brier Score Data
The Brier scores table includes:
- Platform name, type, and region
- Number of completed games analyzed
- Total number of predictions made
- Brier score (lower is better, 0 = perfect, 1 = worst)
- Average predicted probability
- Number of correct predictions
- Overall accuracy percentage

## Understanding Brier Scores

Brier scores measure the accuracy of probabilistic predictions:
- **Perfect Score**: 0.0 (always predicted the correct probability)
- **Worst Score**: 1.0 (always predicted the opposite outcome with 100% confidence)
- **Random Guessing**: ~0.25 (for binary outcomes)
- **Good Performance**: Typically < 0.20 for sports predictions

Lower Brier scores indicate better calibrated and more accurate predictions.