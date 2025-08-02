-- Database schema for sports odds analysis platform
-- Supports binary outcomes (MLB) and ternary outcomes (soccer)

-- Teams table for canonical team data
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100) NOT NULL UNIQUE, -- 'Boston Red Sox', 'New York Yankees', etc.
    sport VARCHAR(50) NOT NULL, -- 'mlb', 'premier_league', etc.
    league VARCHAR(100) NOT NULL, -- 'Major League Baseball', 'English Premier League', etc.
    abbreviation VARCHAR(10), -- 'BOS', 'NYY', etc.
    keywords TEXT[], -- Array of keywords/aliases for matching
    city VARCHAR(100), -- 'Boston', 'New York', etc.
    nickname VARCHAR(100), -- 'Red Sox', 'Yankees', etc.
    timezone VARCHAR(50), -- DST-aware timezone like 'America/New_York', 'America/Los_Angeles'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(sport, canonical_name)
);

-- Core games table - standardized entity for cross-platform matching
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    sport VARCHAR(50) NOT NULL, -- 'mlb', 'premier_league', etc.
    league VARCHAR(100) NOT NULL,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    game_date_local DATE NOT NULL, -- Date in home team's local timezone
    game_start_time TIMESTAMPTZ NOT NULL, -- UTC timezone-aware datetime
    game_start_time_local TIMESTAMPTZ, -- Local timezone-aware datetime (home team's timezone)
    -- Team relationships
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
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
    
    UNIQUE(game_id, platform_id, market_type)
);

-- Individual outcomes within each market (e.g., 'home_win', 'away_win', 'draw')
CREATE TABLE outcomes (
    id SERIAL PRIMARY KEY,
    market_id INTEGER NOT NULL REFERENCES markets(id),
    outcome_type VARCHAR(50) NOT NULL, -- 'home_win', 'away_win', 'draw'
    outcome_name VARCHAR(255) NOT NULL, -- Original outcome name from platform
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(market_id, outcome_type)
);

-- Time-series odds data - one snapshot per outcome per timestamp
CREATE TABLE odds_snapshots (
    id SERIAL PRIMARY KEY,
    outcome_id INTEGER NOT NULL REFERENCES outcomes(id),
    timestamp TIMESTAMPTZ NOT NULL,
    decimal_odds DECIMAL(10, 4) NOT NULL, -- Raw odds from platform
    raw_probability DECIMAL(8, 6), -- 1/decimal_odds
    devigged_probability DECIMAL(8, 6), -- Normalized probability after de-vigging
    devigged_decimal_odds DECIMAL(10, 4), -- 1/devigged_probability
    is_closing_line BOOLEAN DEFAULT FALSE, -- True for final odds before game start
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate odds at same timestamp for same outcome
    UNIQUE(outcome_id, timestamp)
);

-- Indexes for better performance
CREATE INDEX idx_teams_sport_keywords ON teams USING GIN (keywords);
CREATE INDEX idx_games_team_ids ON games(home_team_id, away_team_id);
CREATE INDEX idx_games_sport_start_time ON games(sport, game_start_time);
CREATE INDEX idx_games_status_outcome ON games(game_status, actual_outcome);
CREATE INDEX idx_markets_game_platform ON markets(game_id, platform_id);
CREATE INDEX idx_outcomes_market_type ON outcomes(market_id, outcome_type);
CREATE INDEX idx_odds_outcome_timestamp ON odds_snapshots(outcome_id, timestamp);
CREATE INDEX idx_odds_timestamp ON odds_snapshots(timestamp);
CREATE INDEX idx_odds_closing_lines ON odds_snapshots(is_closing_line) WHERE is_closing_line = TRUE;

-- Comments for clarity
COMMENT ON TABLE teams IS 'Canonical team data with keywords and timezone information';
COMMENT ON TABLE games IS 'Standardized game entities that markets from all platforms link to';
COMMENT ON TABLE platforms IS 'Betting platforms and prediction markets';
COMMENT ON TABLE markets IS 'Platform-specific markets for each game';
COMMENT ON TABLE outcomes IS 'Individual betting outcomes within each market';
COMMENT ON TABLE odds_snapshots IS 'Time-series odds data with raw and de-vigged probabilities';

COMMENT ON COLUMN games.game_start_time IS 'Game start time in UTC';
COMMENT ON COLUMN games.game_start_time_local IS 'Game start time in home team''s local timezone';
COMMENT ON COLUMN games.game_date_local IS 'Game date in home team''s local timezone';
COMMENT ON COLUMN teams.timezone IS 'IANA timezone identifier (e.g., America/New_York) for DST handling';