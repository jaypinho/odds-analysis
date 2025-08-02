-- Migration: Insert MLB teams data
-- This migration populates the teams table with all 30 MLB teams
-- Run this after creating the teams table structure

-- Insert MLB teams with their keywords, abbreviations, and timezones
INSERT INTO teams (canonical_name, sport, league, abbreviation, keywords, city, nickname, timezone) VALUES

-- American League East
('Boston Red Sox', 'mlb', 'Major League Baseball', 'BOS', ARRAY['red sox', 'redsox', 'boston red sox', 'boston'], 'Boston', 'Red Sox', 'America/New_York'),
('New York Yankees', 'mlb', 'Major League Baseball', 'NYY', ARRAY['new york yankees', 'yankees', 'yanks', 'ny yankees', 'new york y'], 'New York', 'Yankees', 'America/New_York'),
('Tampa Bay Rays', 'mlb', 'Major League Baseball', 'TB', ARRAY['tampa bay rays', 'tampa bay', 'rays'], 'Tampa Bay', 'Rays', 'America/New_York'),
('Toronto Blue Jays', 'mlb', 'Major League Baseball', 'TOR', ARRAY['toronto blue jays', 'blue jays', 'bluejays', 'toronto'], 'Toronto', 'Blue Jays', 'America/Toronto'),
('Baltimore Orioles', 'mlb', 'Major League Baseball', 'BAL', ARRAY['baltimore orioles', 'orioles', 'baltimore'], 'Baltimore', 'Orioles', 'America/New_York'),

-- American League Central  
('Chicago White Sox', 'mlb', 'Major League Baseball', 'CWS', ARRAY['chicago white sox', 'white sox', 'whitesox', 'chicago w', 'chicago ws'], 'Chicago', 'White Sox', 'America/Chicago'),
('Cleveland Guardians', 'mlb', 'Major League Baseball', 'CLE', ARRAY['cleveland guardians', 'guardians', 'cleveland'], 'Cleveland', 'Guardians', 'America/New_York'),
('Detroit Tigers', 'mlb', 'Major League Baseball', 'DET', ARRAY['detroit tigers', 'tigers', 'detroit'], 'Detroit', 'Tigers', 'America/New_York'),
('Kansas City Royals', 'mlb', 'Major League Baseball', 'KC', ARRAY['kansas city royals', 'kansas city', 'royals'], 'Kansas City', 'Royals', 'America/Chicago'),
('Minnesota Twins', 'mlb', 'Major League Baseball', 'MIN', ARRAY['minnesota twins', 'twins', 'minnesota'], 'Minnesota', 'Twins', 'America/Chicago'),

-- American League West
('Houston Astros', 'mlb', 'Major League Baseball', 'HOU', ARRAY['houston astros', 'astros', 'houston'], 'Houston', 'Astros', 'America/Chicago'),
('Los Angeles Angels', 'mlb', 'Major League Baseball', 'LAA', ARRAY['los angeles angels', 'la angels', 'angels', 'los angeles a'], 'Los Angeles', 'Angels', 'America/Los_Angeles'),
('Oakland Athletics', 'mlb', 'Major League Baseball', 'OAK', ARRAY['oakland athletics', 'athletics', 'oakland', 'a''s'], 'Oakland', 'Athletics', 'America/Los_Angeles'),
('Seattle Mariners', 'mlb', 'Major League Baseball', 'SEA', ARRAY['seattle mariners', 'mariners', 'seattle'], 'Seattle', 'Mariners', 'America/Los_Angeles'),
('Texas Rangers', 'mlb', 'Major League Baseball', 'TEX', ARRAY['texas rangers', 'rangers', 'texas'], 'Texas', 'Rangers', 'America/Chicago'),

-- National League East
('Atlanta Braves', 'mlb', 'Major League Baseball', 'ATL', ARRAY['atlanta braves', 'braves', 'atlanta'], 'Atlanta', 'Braves', 'America/New_York'),
('Miami Marlins', 'mlb', 'Major League Baseball', 'MIA', ARRAY['miami marlins', 'marlins', 'miami'], 'Miami', 'Marlins', 'America/New_York'),
('New York Mets', 'mlb', 'Major League Baseball', 'NYM', ARRAY['new york mets', 'ny mets', 'mets', 'new york m'], 'New York', 'Mets', 'America/New_York'),
('Philadelphia Phillies', 'mlb', 'Major League Baseball', 'PHI', ARRAY['philadelphia phillies', 'phillies', 'philadelphia'], 'Philadelphia', 'Phillies', 'America/New_York'),
('Washington Nationals', 'mlb', 'Major League Baseball', 'WAS', ARRAY['washington nationals', 'nationals', 'washington'], 'Washington', 'Nationals', 'America/New_York'),

-- National League Central
('Chicago Cubs', 'mlb', 'Major League Baseball', 'CHC', ARRAY['chicago cubs', 'cubs', 'chicago c'], 'Chicago', 'Cubs', 'America/Chicago'),
('Cincinnati Reds', 'mlb', 'Major League Baseball', 'CIN', ARRAY['cincinnati reds', 'reds', 'cincinnati'], 'Cincinnati', 'Reds', 'America/New_York'),
('Milwaukee Brewers', 'mlb', 'Major League Baseball', 'MIL', ARRAY['milwaukee brewers', 'brewers', 'milwaukee'], 'Milwaukee', 'Brewers', 'America/Chicago'),
('Pittsburgh Pirates', 'mlb', 'Major League Baseball', 'PIT', ARRAY['pittsburgh pirates', 'pirates', 'pittsburgh'], 'Pittsburgh', 'Pirates', 'America/New_York'),
('St. Louis Cardinals', 'mlb', 'Major League Baseball', 'STL', ARRAY['st. louis cardinals', 'st louis cardinals', 'cardinals', 'st. louis', 'st louis'], 'St. Louis', 'Cardinals', 'America/Chicago'),

-- National League West
('Arizona Diamondbacks', 'mlb', 'Major League Baseball', 'ARI', ARRAY['arizona diamondbacks', 'diamondbacks', 'arizona', 'dbacks'], 'Arizona', 'Diamondbacks', 'America/Phoenix'),
('Colorado Rockies', 'mlb', 'Major League Baseball', 'COL', ARRAY['colorado rockies', 'rockies', 'colorado'], 'Colorado', 'Rockies', 'America/Denver'),
('Los Angeles Dodgers', 'mlb', 'Major League Baseball', 'LAD', ARRAY['los angeles dodgers', 'la dodgers', 'dodgers', 'los angeles d'], 'Los Angeles', 'Dodgers', 'America/Los_Angeles'),
('San Diego Padres', 'mlb', 'Major League Baseball', 'SD', ARRAY['san diego padres', 'padres', 'san diego'], 'San Diego', 'Padres', 'America/Los_Angeles'),
('San Francisco Giants', 'mlb', 'Major League Baseball', 'SF', ARRAY['san francisco giants', 'sf giants', 'giants', 'san francisco'], 'San Francisco', 'Giants', 'America/Los_Angeles')

-- Handle conflicts in case teams already exist
ON CONFLICT (canonical_name) DO UPDATE SET
    sport = EXCLUDED.sport,
    league = EXCLUDED.league,
    abbreviation = EXCLUDED.abbreviation,
    keywords = EXCLUDED.keywords,
    city = EXCLUDED.city,
    nickname = EXCLUDED.nickname,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;