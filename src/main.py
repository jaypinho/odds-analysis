"""Main orchestration script for odds collection and analysis."""

import os
import sys
import schedule
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import db_manager
from src.collectors.the_odds_api import TheOddsAPICollector
from src.collectors.polymarket import PolymarketCollector
from src.collectors.kalshi import KalshiCollector
from src.models.game import Game
from src.utils.odds import devig_odds


class OddsAnalysisOrchestrator:
    def __init__(self):
        self.odds_api = TheOddsAPICollector()
        self.polymarket = PolymarketCollector()
        self.kalshi = KalshiCollector()
        
    def collect_all_data(self):
        """Collect odds data from all platforms."""
        print(f"Starting data collection at {datetime.now()}")
        
        try:
            # First, update completed games before collecting odds
            # This prevents storing odds for games that are already finished
            self._update_completed_games()
            
            # Then, collect from Polymarket to create game entities as specified in CLAUDE.md
            self._collect_polymarket_data()
            
            # Then collect from Kalshi (links to existing games)
            self._collect_kalshi_data()
            
            # Finally collect from The Odds API (sportsbooks) (links to existing games)
            self._collect_sportsbook_data()
            
            print(f"Data collection completed at {datetime.now()}")
            
        except Exception as e:
            print(f"Error during data collection: {e}")
    
    def _collect_sportsbook_data(self):
        """Collect data from sportsbooks via The Odds API."""
        print("Collecting sportsbook data...")
        
        all_odds = self.odds_api.collect_all_odds()
        
        for region, odds_data in all_odds.items():
            for game_data in odds_data:
                try:
                    # Extract game info from odds data
                    normalized_game = self.odds_api.normalize_game_data(game_data)
                    
                    # Try to find existing game using fuzzy matching (don't create new ones)
                    existing_games_query = """
                        SELECT * FROM games 
                        WHERE sport = 'mlb' 
                        AND game_start_time BETWEEN %s - INTERVAL '3 hours' AND %s + INTERVAL '3 hours'
                    """
                    game_time = normalized_game['game_start_time']
                    existing_games_result = db_manager.execute_query(existing_games_query, (game_time, game_time))
                    
                    existing_games = []
                    if existing_games_result:
                        for row in existing_games_result:
                            existing_games.append(dict(zip([
                                'id', 'sport', 'league', 'home_team', 'away_team',
                                'game_date', 'game_start_time', 'home_team_normalized',
                                'away_team_normalized', 'season', 'actual_outcome',
                                'home_score', 'away_score', 'game_status', 'created_at', 'updated_at'
                            ], row)))
                    
                    # Debug: Show what games are available in the time window
                    if not existing_games:
                        print(f"DEBUG: No games found in database within 3 hours of {game_time}")
                        # Check if there are any games at all
                        all_games_query = "SELECT home_team, away_team, game_start_time FROM games WHERE sport = 'mlb' ORDER BY game_start_time DESC LIMIT 5"
                        all_games_result = db_manager.execute_query(all_games_query, ())
                        if all_games_result:
                            print("DEBUG: Recent games in database:")
                            for row in all_games_result:
                                print(f"  {row[1]} @ {row[0]} at {row[2]}")
                        else:
                            print("DEBUG: No MLB games found in database at all!")
                    else:
                        print(f"DEBUG: Found {len(existing_games)} games in time window for matching")
                        for game in existing_games:
                            print(f"  {game['away_team']} @ {game['home_team']} at {game['game_start_time']}")
                    
                    # Use fuzzy matching to find the right game
                    matched_game = self.odds_api.find_matching_game_fuzzy(game_data, existing_games)
                    
                    if not matched_game:
                        print(f"No matching game found for sportsbook data: {game_data.get('home_team')} vs {game_data.get('away_team')} at {game_time}")
                        continue
                    
                    # Convert dict back to Game object
                    game = Game(**matched_game)
                    
                    if not game or not game.id:
                        print(f"Failed to create/find game for {game_data.get('id', 'unknown')}")
                        continue
                    
                    # Normalize and store odds
                    normalized_odds = self.odds_api.normalize_odds_data(game_data, region)
                    if normalized_odds:
                        self._store_odds_data(game.id, normalized_odds)
                    
                except Exception as e:
                    print(f"Error processing sportsbook game {game_data.get('id', 'unknown')}: {e}")
                    import traceback
                    traceback.print_exc()
    
    def _collect_polymarket_data(self):
        """Collect data from Polymarket."""
        print("Collecting Polymarket data...")
        
        try:
            events = self.polymarket.collect_mlb_events()
            print(f"DEBUG: Polymarket returned {len(events)} events")
            
            games_created = 0
            for event_data in events:
                try:
                    # Check if we have game info
                    game_info = event_data.get('game_info')
                    if not game_info:
                        continue
                    
                    # Get markets for odds collection
                    markets = event_data.get('markets', [])
                    if not markets:
                        continue
                    
                    # Use game start time from game_info (extracted from Polymarket data)
                    reference_time = game_info.get('game_start_time')
                    if not reference_time:
                        print(f"No game start time found for Polymarket event: {event_data.get('title', 'Unknown')}")
                        continue
                    
                    # Create game data from Polymarket event info
                    game_data = {
                        'sport': 'mlb',
                        'league': 'Major League Baseball',
                        'home_team': game_info.get('home_team', game_info['teams'][0]),  # Use explicit home team if available
                        'away_team': game_info.get('away_team', game_info['teams'][1]),  # Use explicit away team if available
                        'game_start_time': reference_time
                    }
                    
                    # Create or find the game - this is the canonical game entity
                    game = Game.find_or_create(game_data)
                    if not game:
                        print(f"Failed to create/find game for teams: {game_info['teams']}")
                        continue
                    
                    print(f"Created/found game {game.id}: {game.away_team} @ {game.home_team} at {game.game_start_time}")
                    print(f"DEBUG: Game time timezone info: {game.game_start_time.tzinfo if hasattr(game.game_start_time, 'tzinfo') else 'No tzinfo'}")
                    games_created += 1
                    
                    # Process each market in the event (don't break after first one)
                    all_market_odds = []
                    
                    for market in markets:
                        try:
                            clob_token_ids_str = market.get('clobTokenIds')
                            if not clob_token_ids_str:
                                continue
                            
                            # Parse the JSON string to get the actual token IDs
                            try:
                                clob_token_ids = json.loads(clob_token_ids_str)
                                if not clob_token_ids or len(clob_token_ids) == 0:
                                    continue
                            except (json.JSONDecodeError, TypeError) as e:
                                print(f"Error parsing clobTokenIds: {e}")
                                continue
                            
                            # Process all CLOB token IDs (each represents a "Yes" outcome for different teams)
                            for i, token_id in enumerate(clob_token_ids):
                                # Get prices from CLOB API
                                price_data = self.polymarket.get_market_prices(token_id)
                                if not price_data:
                                    continue
                                
                                    # Store Polymarket odds for this game
                                normalized_odds = self.polymarket.normalize_odds_data(event_data, market, price_data, token_index=i)
                                
                                if normalized_odds:
                                    # Add platform info
                                    for odds in normalized_odds:
                                        odds['platform_key'] = 'polymarket'
                                        odds['region'] = None
                                    
                                    # Collect all odds instead of storing immediately
                                    all_market_odds.extend(normalized_odds)
                        
                        except Exception as market_e:
                            print(f"Error processing market {market.get('question', 'unknown')}: {market_e}")
                            continue
                    
                    # Store all collected odds for this game
                    if all_market_odds:
                        self._store_odds_data(game.id, all_market_odds)
                        print(f"Stored {len(all_market_odds)} Polymarket odds for game {game.id}: {game.away_team} @ {game.home_team}")
                    
                except Exception as e:
                    print(f"Error processing Polymarket event {event_data.get('id', 'unknown')}: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"DEBUG: Polymarket processing complete. Created/found {games_created} games total")
                    
        except Exception as e:
            print(f"Error collecting Polymarket data: {e}")
    
    def _find_game_by_teams(self, team_names: List[str], reference_time: Optional[datetime] = None) -> Optional['Game']:
        """Find a game in the database by team names with optional time-based matching."""
        from src.models.game import Game
        
        if len(team_names) != 2:
            return None
        
        # Find teams in database
        from src.models.team import Team
        team_objects = [Team.find_team_by_name(team, 'mlb') for team in team_names]
        if not all(team_objects):
            return None
        normalized_teams = [team.canonical_name for team in team_objects]
        
        if reference_time:
            # When we have a reference time (e.g., from Polymarket gameStartTime), 
            # find the game that's closest to that time within a reasonable tolerance
            query = """
                SELECT *, 
                       ABS(EXTRACT(EPOCH FROM (game_start_time - %s))) as time_diff_seconds
                FROM games 
                WHERE sport = 'mlb'
                AND game_start_time BETWEEN %s - INTERVAL '48 hours' AND %s + INTERVAL '24 hours'
                AND (
                    (home_team_id = %s AND away_team_id = %s) OR
                    (home_team_id = %s AND away_team_id = %s)
                )
                ORDER BY ABS(EXTRACT(EPOCH FROM (game_start_time - %s))) ASC
                LIMIT 1
            """
            
            result = db_manager.execute_query(query, (
                reference_time, reference_time, reference_time,
                team_objects[0].id, team_objects[1].id,
                team_objects[1].id, team_objects[0].id,
                reference_time
            ))
        else:
            # Fallback to time-agnostic matching (original behavior)
            query = """
                SELECT *, 
                       ABS(EXTRACT(EPOCH FROM (game_start_time - NOW()))) as time_diff_seconds
                FROM games 
                WHERE sport = 'mlb'
                AND game_start_time > NOW() - INTERVAL '24 hours'
                AND (
                    (home_team_id = %s AND away_team_id = %s) OR
                    (home_team_id = %s AND away_team_id = %s)
                )
                ORDER BY 
                    CASE 
                        WHEN game_start_time > NOW() THEN 1  -- Prioritize future games
                        ELSE 2  -- Then recent past games
                    END,
                    ABS(EXTRACT(EPOCH FROM (game_start_time - NOW()))) ASC
                LIMIT 1
            """
            
            result = db_manager.execute_query(query, (
                team_objects[0].id, team_objects[1].id,
                team_objects[1].id, team_objects[0].id
            ))
        
        if result:
            # Get the time difference in seconds from the query result
            time_diff_seconds = result[0][-1]  # Last column is time_diff_seconds
            
            # Apply tolerance check when we have a reference time
            if reference_time and time_diff_seconds > 7200:  # 2 hours = 7200 seconds
                time_diff_hours = time_diff_seconds / 3600
                print(f"Rejecting game match with {time_diff_hours:.1f} hour time difference (exceeds 2-hour tolerance)")
                return None
            
            # Remove the time_diff_seconds column from result before creating Game object
            game_data = result[0][:-1]  # Exclude last column (time_diff_seconds)
            game = Game(**dict(zip([
                'id', 'sport', 'league', 'home_team', 'away_team',
                'game_date', 'game_start_time', 'home_team_id', 'away_team_id',
                'home_team_normalized', 'away_team_normalized', 'season', 'actual_outcome',
                'home_score', 'away_score', 'game_status', 'created_at', 'updated_at'
            ], game_data)))
            
            if reference_time:
                time_diff_hours = time_diff_seconds / 3600
                print(f"Matched game with {time_diff_hours:.1f} hour time difference: {game.away_team} @ {game.home_team} on {game.game_start_time}")
            
            return game
        
        return None
    
    def _collect_kalshi_data(self):
        """Collect data from Kalshi."""
        print("Collecting Kalshi data...")
        
        try:
            markets = self.kalshi.collect_baseball_markets()
            
            for market_data in markets:
                try:
                    # Check if we have game info
                    game_info = market_data.get('game_info')
                    if not game_info:
                        continue
                    
                    # Get orderbook for current prices
                    ticker = market_data.get('ticker')
                    if not ticker:
                        continue
                    
                    orderbook = self.kalshi.get_market_orderbook(ticker)
                    if not orderbook:
                        continue
                    
                    # Try to find existing game in database using game start time from Kalshi data
                    game_start_time = game_info.get('game_start_time')
                    if game_start_time:
                        game = self._find_game_by_teams(game_info['teams'], game_start_time)
                    else:
                        game = self._find_game_by_teams(game_info['teams'])
                    
                    if not game:
                        if game_start_time:
                            print(f"No matching game found for Kalshi teams: {game_info['teams']} at {game_start_time}")
                        else:
                            print(f"No matching game found for Kalshi teams: {game_info['teams']}")
                        continue
                    
                    # Store Kalshi odds for this game
                    normalized_odds = self.kalshi.normalize_odds_data(market_data, orderbook)
                    
                    if normalized_odds:
                        # Add platform info
                        for odds in normalized_odds:
                            odds['platform_key'] = 'kalshi'
                            odds['region'] = None
                        
                        self._store_odds_data(game.id, normalized_odds)
                        print(f"Stored Kalshi odds for game {game.id}: {game.away_team} @ {game.home_team}")
                    
                except Exception as e:
                    print(f"Error processing Kalshi market {market_data.get('ticker', 'unknown')}: {e}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"Error collecting Kalshi data: {e}")
    
    def _store_odds_data(self, game_id: int, odds_data: List[Dict[str, Any]]):
        """Store odds data in database with de-vigging."""
        if not odds_data or not game_id:
            return
        
        # Verify game exists and check if it's completed
        verify_query = "SELECT id, game_status FROM games WHERE id = %s"
        result = db_manager.execute_query(verify_query, (game_id,))
        if not result:
            print(f"Warning: Game ID {game_id} not found in database, skipping odds storage")
            return
        
        game_status = result[0][1]
        if game_status == 'completed':
            print(f"Warning: Game ID {game_id} is already completed, skipping odds storage")
            return
        
        # Group odds by platform and apply de-vigging
        platform_odds = {}
        for odds in odds_data:
            platform_key = f"{odds['platform_key']}_{odds['region']}"
            if platform_key not in platform_odds:
                platform_odds[platform_key] = []
            platform_odds[platform_key].append(odds)
        
        # Process each platform's odds
        for platform_key, platform_data in platform_odds.items():
            try:
                # Apply de-vigging
                devigged_data = devig_odds(platform_data)
                
                # Store in database
                for odds in devigged_data:
                    self._insert_odds_snapshot(game_id, odds)
                    
            except Exception as e:
                print(f"Error storing odds for platform {platform_key}: {e}")
                import traceback
                traceback.print_exc()
    
    def _insert_odds_snapshot(self, game_id: int, odds_data: Dict[str, Any]):
        """Insert single odds snapshot into database with duplicate prevention."""
        try:
            # Double-check that the game is not completed before inserting odds
            game_status_query = "SELECT game_status FROM games WHERE id = %s"
            game_status_result = db_manager.execute_query(game_status_query, (game_id,))
            if game_status_result and game_status_result[0][0] == 'completed':
                print(f"Skipping odds insertion for completed game {game_id}")
                return
            
            # Determine platform type based on platform key
            platform_type = 'prediction_market' if odds_data['platform_key'] in ['polymarket', 'kalshi'] else 'sportsbook'
            
            # First, find or create platform
            platform_id = self._get_or_create_platform(
                odds_data['platform_key'], 
                platform_type, 
                odds_data.get('region')
            )
            
            # Find or create market
            market_id = self._get_or_create_market(
                game_id, 
                platform_id, 
                odds_data['platform_name'],
                odds_data['market_type'],
                odds_data.get('identifier')  # Will be slug/event_ticker/id depending on platform
            )
            
            # Find or create outcome
            outcome_id = self._get_or_create_outcome(
                market_id,
                odds_data['outcome_type'],
                odds_data['outcome_name']
            )
            
            # Check if we already have odds for this outcome within the last minute
            # This prevents duplicate storage of the same odds data
            duplicate_check_query = """
                SELECT id FROM odds_snapshots 
                WHERE outcome_id = %s 
                AND timestamp > %s - INTERVAL '1 minute'
                AND ABS(decimal_odds - %s) < 0.0001
                LIMIT 1
            """
            
            existing_odds = db_manager.execute_query(duplicate_check_query, (
                outcome_id,
                odds_data['timestamp'],
                odds_data['decimal_odds']
            ))
            
            if existing_odds:
                print(f"Skipping duplicate odds for outcome_id {outcome_id}: odds {odds_data['decimal_odds']} already exists within 1 minute")
                return
            
            # Insert odds snapshot
            query = """
                INSERT INTO odds_snapshots (
                    outcome_id, timestamp, decimal_odds, raw_probability,
                    devigged_probability, devigged_decimal_odds
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            raw_probability = 1 / odds_data['decimal_odds'] if odds_data['decimal_odds'] > 0 else 0
            
            db_manager.execute_query(query, (
                outcome_id,
                odds_data['timestamp'],
                odds_data['decimal_odds'],
                raw_probability,
                odds_data.get('devigged_probability'),
                odds_data.get('devigged_decimal_odds')
            ))
            
        except Exception as e:
            print(f"Error in _insert_odds_snapshot: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _get_or_create_platform(self, name: str, platform_type: str, region: str = None) -> int:
        """Get or create platform and return ID."""
        # Handle NULL regions properly in the query
        if region is None:
            query = "SELECT id FROM platforms WHERE name = %s AND region IS NULL"
            params = (name,)
        else:
            query = "SELECT id FROM platforms WHERE name = %s AND region = %s"
            params = (name, region)
        
        result = db_manager.execute_query(query, params)
        
        if result:
            return result[0][0]
        
        # Create new platform
        query = """
            INSERT INTO platforms (name, platform_type, region) 
            VALUES (%s, %s, %s) 
            RETURNING id
        """
        result = db_manager.execute_query(query, (name, platform_type, region))
        return result[0][0]
    
    def _get_or_create_market(self, game_id: int, platform_id: int, market_name: str, market_type: str, identifier: str = None) -> int:
        """Get or create market and return ID."""
        query = """
            SELECT id FROM markets 
            WHERE game_id = %s AND platform_id = %s AND market_type = %s
        """
        result = db_manager.execute_query(query, (game_id, platform_id, market_type))
        
        if result:
            return result[0][0]
        
        # Create new market
        query = """
            INSERT INTO markets (game_id, platform_id, platform_market_id, identifier, market_name, market_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = db_manager.execute_query(query, (
            game_id, platform_id, f"{platform_id}_{game_id}_{market_type}", identifier, market_name, market_type
        ))
        return result[0][0]
    
    def _get_or_create_outcome(self, market_id: int, outcome_type: str, outcome_name: str) -> int:
        """Get or create outcome and return ID."""
        query = "SELECT id FROM outcomes WHERE market_id = %s AND outcome_type = %s"
        result = db_manager.execute_query(query, (market_id, outcome_type))
        
        if result:
            return result[0][0]
        
        # Create new outcome
        query = """
            INSERT INTO outcomes (market_id, outcome_type, outcome_name)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        result = db_manager.execute_query(query, (market_id, outcome_type, outcome_name))
        return result[0][0]
    
    def _update_completed_games(self):
        """Update outcomes for completed games."""
        print("Updating completed games...")
        
        # Get recent scores from The Odds API
        scores = self.odds_api.get_scores(days_from=3)
        
        for score_data in scores:
            if score_data.get('completed'):
                try:
                    normalized_game = self.odds_api.normalize_game_data(score_data)
                    
                    # Find the game in our database
                    game = Game.find_or_create(normalized_game)
                    
                    # Update with scores if available
                    scores_data = score_data.get('scores')
                    if scores_data and len(scores_data) >= 2:
                        home_score = None
                        away_score = None
                        
                        for score in scores_data:
                            if score['name'] == score_data['home_team']:
                                home_score = score['score']
                            elif score['name'] == score_data['away_team']:
                                away_score = score['score']
                        
                        if home_score is not None and away_score is not None:
                            game.update_outcome(int(home_score), int(away_score))
                            print(f"Updated game: {game.away_team} @ {game.home_team} - {away_score}-{home_score}")
                
                except Exception as e:
                    print(f"Error updating completed game: {e}")


def main():
    """Main entry point."""
    # Test database connection
    if not db_manager.test_connection():
        print("Failed to connect to database. Exiting.")
        return
    
    # Create orchestrator
    orchestrator = OddsAnalysisOrchestrator()
    
    # Run once immediately
    orchestrator.collect_all_data()
    
    # Schedule regular collection
    collection_interval = int(os.getenv('COLLECTION_INTERVAL_MINUTES', 15))
    schedule.every(collection_interval).minutes.do(orchestrator.collect_all_data)
    
    print(f"Scheduled data collection every {collection_interval} minutes")
    print("Press Ctrl+C to stop")
    
    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()