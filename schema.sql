-- Database schema for sports odds analysis platform
-- Supports binary outcomes (MLB) and ternary outcomes (soccer)

-- Core games table - standardized entity for cross-platform matching
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(50) NOT NULL, -- 'mlb', 'premier_league', etc.
    league VARCHAR(100) NOT NULL,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    game_date DATE NOT NULL,
    game_start_time TIMESTAMPTZ NOT NULL,
    -- Standardized team names for matching
    home_team_normalized VARCHAR(100) NOT NULL,
    away_team_normalized VARCHAR(100) NOT NULL,
    season VARCHAR(20), -- '2024', '2024-25', etc.
    -- Actual outcome (null until game completes)
    actual_outcome VARCHAR(20), -- 'home_win', 'away_win', 'draw'
    home_score INTEGER,
    away_score INTEGER,
    game_status VARCHAR(20) DEFAULT 'scheduled', -- 'scheduled', 'completed', 'cancelled'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(sport, home_team_normalized, away_team_normalized, game_start_time)
);

-- Platforms/sportsbooks
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL, -- 'polymarket', 'kalshi', 'draftkings', etc.
    platform_type VARCHAR(50) NOT NULL, -- 'prediction_market', 'sportsbook'
    region VARCHAR(10), -- 'us', 'eu', null for prediction markets
    api_base_url VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(name, region)
);

-- Markets on each platform for each game
CREATE TABLE markets (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id),
    platform_id INTEGER NOT NULL REFERENCES platforms(id),
    platform_market_id VARCHAR(255) NOT NULL, -- External ID from platform
    identifier VARCHAR(255), -- slug (Polymarket), event_ticker (Kalshi), or id (Odds API)
    market_name VARCHAR(255) NOT NULL, -- Original market name from platform
    market_type VARCHAR(50) NOT NULL, -- 'moneyline', 'match_winner', etc.
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(platform_id, platform_market_id)
);

-- Individual betting outcomes within each market
CREATE TABLE outcomes (
    id SERIAL PRIMARY KEY,
    market_id INTEGER NOT NULL REFERENCES markets(id),
    outcome_type VARCHAR(50) NOT NULL, -- 'home_win', 'away_win', 'draw'
    outcome_name VARCHAR(255) NOT NULL, -- Original name from platform
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(market_id, outcome_type)
);

-- Odds snapshots over time for each outcome
CREATE TABLE odds_snapshots (
    id SERIAL PRIMARY KEY,
    outcome_id INTEGER NOT NULL REFERENCES outcomes(id),
    timestamp TIMESTAMPTZ NOT NULL,
    -- Raw odds in different formats
    decimal_odds DECIMAL(10,4), -- European decimal odds (e.g., 1.85)
    american_odds INTEGER, -- American odds (e.g., -120, +150)
    raw_probability DECIMAL(5,4), -- Raw implied probability (0.0000 to 1.0000)
    -- De-vigged odds (normalized to sum to 1.0 across all outcomes)
    devigged_probability DECIMAL(5,4), -- De-vigged probability (0.0000 to 1.0000)
    devigged_decimal_odds DECIMAL(10,4), -- Decimal odds derived from de-vigged probability
    -- Volume/liquidity indicators where available
    volume DECIMAL(15,2),
    total_matched DECIMAL(15,2), -- For prediction markets
    -- Closing line indicator
    is_closing_line BOOLEAN DEFAULT FALSE, -- True if this is the final odds before game start
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_games_sport_date ON games(sport, game_date);
CREATE INDEX idx_games_start_time ON games(game_start_time);
CREATE INDEX idx_games_normalized_teams ON games(home_team_normalized, away_team_normalized);
CREATE INDEX idx_odds_snapshots_timestamp ON odds_snapshots(timestamp);
CREATE INDEX idx_odds_snapshots_outcome_time ON odds_snapshots(outcome_id, timestamp);
CREATE INDEX idx_odds_snapshots_closing_line ON odds_snapshots(is_closing_line) WHERE is_closing_line = TRUE;

-- Insert initial platforms
INSERT INTO platforms (name, platform_type, region) VALUES
('polymarket', 'prediction_market', NULL),
('kalshi', 'prediction_market', NULL),
('predictit', 'prediction_market', NULL);

-- Sportsbooks will be added dynamically from The Odds API