"""Game model for database operations."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.config.database import db_manager
from src.utils.teams import normalize_team_name_for_matching


class Game:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.sport = kwargs.get('sport')
        self.league = kwargs.get('league')
        self.home_team = kwargs.get('home_team')
        self.away_team = kwargs.get('away_team')
        self.game_date = kwargs.get('game_date')
        self.game_start_time = kwargs.get('game_start_time')
        self.home_team_normalized = kwargs.get('home_team_normalized')
        self.away_team_normalized = kwargs.get('away_team_normalized')
        self.season = kwargs.get('season')
        self.actual_outcome = kwargs.get('actual_outcome')
        self.home_score = kwargs.get('home_score')
        self.away_score = kwargs.get('away_score')
        self.game_status = kwargs.get('game_status', 'scheduled')
    
    @classmethod
    def find_or_create(cls, game_data: Dict[str, Any]) -> 'Game':
        """Find existing game or create new one."""
        normalized_home = cls.normalize_team_name(game_data['home_team'])
        normalized_away = cls.normalize_team_name(game_data['away_team'])
        
        # Try to find existing game
        query = """
            SELECT * FROM games 
            WHERE sport = %s 
            AND home_team_normalized = %s 
            AND away_team_normalized = %s 
            AND game_start_time = %s
        """
        
        result = db_manager.execute_query(query, (
            game_data['sport'],
            normalized_home,
            normalized_away,
            game_data['game_start_time']
        ))
        
        if result:
            return cls(**dict(zip([
                'id', 'sport', 'league', 'home_team', 'away_team',
                'game_date', 'game_start_time', 'home_team_normalized',
                'away_team_normalized', 'season', 'actual_outcome',
                'home_score', 'away_score', 'game_status', 'created_at', 'updated_at'
            ], result[0])))
        
        # Create new game
        return cls.create(game_data)
    
    @classmethod
    def create(cls, game_data: Dict[str, Any]) -> 'Game':
        """Create new game in database."""
        try:
            normalized_home = cls.normalize_team_name(game_data['home_team'])
            normalized_away = cls.normalize_team_name(game_data['away_team'])
            
            query = """
                INSERT INTO games (
                    sport, league, home_team, away_team, game_date, 
                    game_start_time, home_team_normalized, away_team_normalized, season
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            
            params = (
                game_data['sport'],
                game_data['league'],
                game_data['home_team'],
                game_data['away_team'],
                game_data['game_start_time'].date(),
                game_data['game_start_time'],
                normalized_home,
                normalized_away,
                game_data.get('season', season)
            )
            
            print(f"Creating game: {game_data['away_team']} @ {game_data['home_team']} at {game_data['game_start_time']}")
            
            result = db_manager.execute_query(query, params)
            
            if result and len(result) > 0:
                game = cls(**dict(zip([
                    'id', 'sport', 'league', 'home_team', 'away_team',
                    'game_date', 'game_start_time', 'home_team_normalized',
                    'away_team_normalized', 'season', 'actual_outcome',
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
        """Normalize team name for cross-platform matching using enhanced utility."""
        return normalize_team_name_for_matching(team_name)
    
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
        # and mark it as the closing line
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
                GROUP BY os.outcome_id
            )
            UPDATE odds_snapshots 
            SET is_closing_line = TRUE
            WHERE (outcome_id, timestamp) IN (
                SELECT outcome_id, max_timestamp FROM latest_odds
            )
        """
        
        db_manager.execute_query(query, (self.id, self.game_start_time))
        print(f"Marked closing lines for game {self.id}")