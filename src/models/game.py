"""Game model for database operations."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.config.database import db_manager
from src.models.team import Team, normalize_team_name_for_matching


class Game:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.sport = kwargs.get('sport')
        self.league = kwargs.get('league')
        self.home_team = kwargs.get('home_team')
        self.away_team = kwargs.get('away_team')
        self.game_date_local = kwargs.get('game_date_local')
        self.game_start_time = kwargs.get('game_start_time')
        self.game_start_time_local = kwargs.get('game_start_time_local')
        self.home_team_id = kwargs.get('home_team_id')
        self.away_team_id = kwargs.get('away_team_id')
        self.home_team_normalized = kwargs.get('home_team_normalized')
        self.away_team_normalized = kwargs.get('away_team_normalized')
        self.season = kwargs.get('season')
        self.actual_outcome = kwargs.get('actual_outcome')
        self.home_score = kwargs.get('home_score')
        self.away_score = kwargs.get('away_score')
        self.game_status = kwargs.get('game_status', 'scheduled')
    
    @classmethod
    def find_or_create(cls, game_data: Dict[str, Any]) -> 'Game':
        """Find existing game or create new one using fuzzy time matching."""
        # Find teams in database
        home_team = Team.find_team_by_name(game_data['home_team'], game_data.get('sport', 'mlb'))
        away_team = Team.find_team_by_name(game_data['away_team'], game_data.get('sport', 'mlb'))
        
        if not home_team or not away_team:
            print(f"Could not find teams in database: home='{game_data['home_team']}' ({home_team}), away='{game_data['away_team']}' ({away_team})")
            return None
        
        # Try to find existing game with fuzzy time matching (within 30 minutes)
        query = """
            SELECT *, 
                   ABS(EXTRACT(EPOCH FROM (game_start_time - %s))) as time_diff_seconds
            FROM games 
            WHERE sport = %s 
            AND home_team_id = %s 
            AND away_team_id = %s 
            AND ABS(EXTRACT(EPOCH FROM (game_start_time - %s))) <= 1800  -- 30 minutes = 1800 seconds
            ORDER BY ABS(EXTRACT(EPOCH FROM (game_start_time - %s))) ASC
            LIMIT 1
        """
        
        result = db_manager.execute_query(query, (
            game_data['game_start_time'],  # For time_diff calculation
            game_data['sport'],
            home_team.id,
            away_team.id,
            game_data['game_start_time'],  # For time comparison
            game_data['game_start_time']   # For ordering
        ))
        
        if result:
            game_row = result[0]
            time_diff_seconds = game_row[-1]  # Last column is time_diff_seconds
            print(f"Found existing game with {time_diff_seconds/60:.1f} minute time difference")
            
            # Return existing game (excluding the time_diff_seconds column)
            return cls(**dict(zip([
                'id', 'sport', 'league', 'home_team', 'away_team',
                'game_date_local', 'game_start_time', 'game_start_time_local', 'home_team_id', 'away_team_id',
                'home_team_normalized', 'away_team_normalized', 'season', 'actual_outcome',
                'home_score', 'away_score', 'game_status', 'created_at', 'updated_at'
            ], game_row[:-1])))  # Exclude the time_diff_seconds column
        
        # Create new game
        return cls.create(game_data, home_team, away_team)
    
    @classmethod
    def create(cls, game_data: Dict[str, Any], home_team: Team, away_team: Team) -> 'Game':
        """Create new game in database."""
        try:
            query = """
                INSERT INTO games (
                    sport, league, home_team, away_team, game_date_local, 
                    game_start_time, game_start_time_local, home_team_id, away_team_id,
                    home_team_normalized, away_team_normalized, season
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """
            
            # Determine season based on game date
            game_year = game_data['game_start_time'].year
            # MLB season typically starts in March/April and ends in October/November
            # So games in Jan-Feb are usually spring training or previous season playoffs
            if game_data['game_start_time'].month <= 2:
                season = str(game_year - 1)  # Early year games are previous season
            else:
                season = str(game_year)
            
            # Ensure game_start_time is in UTC
            game_start_time_utc = cls._ensure_utc_time(game_data['game_start_time'])
            
            # Calculate local game time using home team's timezone
            game_start_time_local = cls._convert_to_local_time(
                game_start_time_utc, 
                home_team.timezone
            )
            
            # Extract local date from local game time
            game_date_local = game_start_time_local.date()
            
            params = (
                game_data['sport'],
                game_data['league'],
                game_data['home_team'],
                game_data['away_team'],
                game_date_local,
                game_start_time_utc,
                game_start_time_local,
                home_team.id,
                away_team.id,
                home_team.canonical_name,  # Store canonical name in normalized field
                away_team.canonical_name,  # Store canonical name in normalized field
                game_data.get('season', season)
            )
            
            print(f"Creating game: {game_data['away_team']} @ {game_data['home_team']} at {game_data['game_start_time']}")
            
            result = db_manager.execute_query(query, params)
            
            if result and len(result) > 0:
                game = cls(**dict(zip([
                    'id', 'sport', 'league', 'home_team', 'away_team',
                    'game_date_local', 'game_start_time', 'game_start_time_local', 'home_team_id', 'away_team_id',
                    'home_team_normalized', 'away_team_normalized', 'season', 'actual_outcome',
                    'home_score', 'away_score', 'game_status', 'created_at', 'updated_at'
                ], result[0])))
                
                print(f"Successfully created game with ID: {game.id}")
                return game
            
            raise Exception("No result returned from INSERT")
            
        except Exception as e:
            print(f"Error creating game: {e}")
            print(f"Game data: {game_data}")
            raise e
    
    @staticmethod
    def normalize_team_name(team_name: str) -> str:
        """Normalize team name for cross-platform matching using database."""
        canonical_name = normalize_team_name_for_matching(team_name)
        return canonical_name if canonical_name else team_name.lower().strip()
    
    def update_outcome(self, home_score: int, away_score: int):
        """Update game with final outcome and mark closing lines."""
        if home_score > away_score:
            outcome = 'home_win'
        elif away_score > home_score:
            outcome = 'away_win'
        else:
            outcome = 'draw'
        
        # Update game outcome
        query = """
            UPDATE games 
            SET actual_outcome = %s, home_score = %s, away_score = %s, 
                game_status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        
        db_manager.execute_query(query, (outcome, home_score, away_score, self.id))
        
        # Mark closing lines for this game
        self._mark_closing_lines()
        
        self.actual_outcome = outcome
        self.home_score = home_score
        self.away_score = away_score
        self.game_status = 'completed'
    
    def _mark_closing_lines(self):
        """Mark the final odds snapshot before game start as closing lines."""
        # For each outcome in each market for this game, find the latest odds before game start
        # that was collected within 1 hour of game start, and mark it as the closing line
        query = """
            WITH latest_odds AS (
                SELECT 
                    os.outcome_id,
                    MAX(os.timestamp) as max_timestamp
                FROM odds_snapshots os
                JOIN outcomes o ON os.outcome_id = o.id
                JOIN markets m ON o.market_id = m.id
                WHERE m.game_id = %s 
                AND os.timestamp <= %s
                AND os.timestamp >= %s - INTERVAL '60 minutes'
                GROUP BY os.outcome_id
            )
            UPDATE odds_snapshots 
            SET is_closing_line = TRUE
            WHERE (outcome_id, timestamp) IN (
                SELECT outcome_id, max_timestamp FROM latest_odds
            )
        """
        
        db_manager.execute_query(query, (self.id, self.game_start_time, self.game_start_time))
        print(f"Marked closing lines for game {self.id}")
    
    @staticmethod
    def _ensure_utc_time(dt):
        """Ensure datetime is timezone-aware and in UTC."""
        from datetime import timezone
        
        if dt.tzinfo is None:
            # Naive datetime - assume it's already UTC
            return dt.replace(tzinfo=timezone.utc)
        elif dt.tzinfo != timezone.utc:
            # Convert to UTC if it's in a different timezone
            return dt.astimezone(timezone.utc)
        else:
            # Already in UTC
            return dt
    
    @staticmethod
    def _convert_to_local_time(utc_time, local_timezone: str):
        """Convert UTC time to local timezone."""
        from datetime import timezone
        import pytz
        
        # Ensure the input time is timezone-aware
        if utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=timezone.utc)
        elif utc_time.tzinfo != timezone.utc:
            # Convert to UTC first if it's in a different timezone
            utc_time = utc_time.astimezone(timezone.utc)
        
        # Convert to local timezone
        local_tz = pytz.timezone(local_timezone)
        return utc_time.astimezone(local_tz)