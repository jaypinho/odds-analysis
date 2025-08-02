"""Data collector for The Odds API."""

import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import time
from src.utils.teams import teams_match_fuzzy, normalize_team_name_for_matching


class TheOddsAPICollector:
    def __init__(self):
        self.api_key = os.getenv('THE_ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("THE_ODDS_API_KEY environment variable is required")
        
        self.base_url = "https://api.the-odds-api.com/v4"
        self.sport = "baseball_mlb"
        self.regions = ["us", "eu"]
        self.markets = ["h2h"]  # head-to-head (moneyline)
        
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with error handling."""
        params['apiKey'] = self.api_key
        
        response = requests.get(f"{self.base_url}/{endpoint}", params=params)
        response.raise_for_status()
        
        # Log remaining requests
        remaining = response.headers.get('x-requests-remaining')
        if remaining:
            print(f"API requests remaining: {remaining}")
        
        return response.json()
    
    def get_upcoming_games(self) -> List[Dict[str, Any]]:
        """Get list of upcoming MLB games."""
        try:
            data = self._make_request("sports/baseball_mlb/events", {})
            return data
        except Exception as e:
            print(f"Error fetching upcoming games: {e}")
            return []
    
    def get_odds_for_games(self, region: str = "us") -> List[Dict[str, Any]]:
        """Get current odds for upcoming MLB games."""
        try:
            params = {
                "regions": region,
                "markets": ",".join(self.markets),
                "oddsFormat": "decimal",
                "dateFormat": "iso"
            }
            
            data = self._make_request(f"sports/{self.sport}/odds", params)
            return data
        except Exception as e:
            print(f"Error fetching odds for region {region}: {e}")
            return []
    
    def get_scores(self, days_from: int = 1) -> List[Dict[str, Any]]:
        """Get recent game scores."""
        try:
            params = {
                "daysFrom": days_from,
                "dateFormat": "iso"
            }
            
            data = self._make_request(f"sports/{self.sport}/scores", params)
            return data
        except Exception as e:
            print(f"Error fetching scores: {e}")
            return []
    
    def collect_all_odds(self) -> Dict[str, List[Dict[str, Any]]]:
        """Collect odds from both US and EU regions as specified in CLAUDE.md."""
        all_odds = {}
        
        for region in self.regions:
            print(f"Collecting MLB odds for region: {region}")
            odds = self.get_odds_for_games(region)
            all_odds[region] = odds
            print(f"Found {len(odds)} games with odds in {region} region")
            
            # Rate limiting between regions
            time.sleep(1)
        
        return all_odds
    
    def normalize_game_data(self, odds_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize game data to standard format (kept for backward compatibility)."""
        return self.extract_game_info_from_odds_data(odds_data)
    
    def extract_game_info_from_odds_data(self, odds_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract game info from The Odds API data using home_team, away_team, and commence_time."""
        return {
            'platform_game_id': odds_data['id'],
            'home_team': odds_data['home_team'],
            'away_team': odds_data['away_team'],
            'game_start_time': datetime.fromisoformat(odds_data['commence_time'].replace('Z', '+00:00')),
            'sport': 'mlb',
            'league': 'Major League Baseball'
        }
    
    def find_matching_game_fuzzy(self, odds_data: Dict[str, Any], existing_games: List[Dict[str, Any]], tolerance_minutes: int = 30) -> Optional[Dict[str, Any]]:
        """Find matching game using fuzzy time matching as specified in CLAUDE.md."""
        home_team = odds_data['home_team']
        away_team = odds_data['away_team']
        commence_time = datetime.fromisoformat(odds_data['commence_time'].replace('Z', '+00:00'))
        
        for game in existing_games:
            # Use fuzzy team matching for better cross-platform compatibility
            game_home = game.get('home_team', '')
            game_away = game.get('away_team', '')
            
            # Check if teams match using fuzzy matching (handles different naming conventions)
            teams_match = (
                teams_match_fuzzy(home_team, game_home) and 
                teams_match_fuzzy(away_team, game_away)
            ) or (
                # Check for swapped home/away (rare but possible)
                teams_match_fuzzy(home_team, game_away) and 
                teams_match_fuzzy(away_team, game_home)
            )
            
            if teams_match:
                # Check time with fuzzy matching (up to 30 minutes as specified)
                game_time = game.get('game_start_time')
                if isinstance(game_time, str):
                    game_time = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                elif isinstance(game_time, datetime):
                    # Game times from Polymarket should already be timezone-aware
                    # If somehow naive, assume UTC (but this shouldn't happen with proper Polymarket data)
                    if game_time.tzinfo is None:
                        game_time = game_time.replace(tzinfo=timezone.utc)
                else:
                    continue  # Invalid time format
                
                # Ensure commence_time is timezone-aware
                if commence_time.tzinfo is None:
                    commence_time = commence_time.replace(tzinfo=timezone.utc)
                
                time_diff = abs((commence_time - game_time).total_seconds() / 60)  # minutes
                
                # Debug the time comparison
                print(f"DEBUG: Comparing times - Sportsbook: {commence_time}, Database: {game_time}, Diff: {time_diff:.1f} minutes")
                
                if time_diff <= tolerance_minutes:
                    return game
        
        return None
    
    def normalize_odds_data(self, odds_data: Dict[str, Any], region: str) -> List[Dict[str, Any]]:
        """Normalize odds data to standard format."""
        normalized_odds = []
        
        for bookmaker in odds_data.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                if market['key'] == 'h2h':  # moneyline market
                    for outcome in market['outcomes']:
                        # Determine outcome type by comparing with home/away teams
                        if outcome['name'] == odds_data['home_team']:
                            outcome_type = 'home_win'
                        elif outcome['name'] == odds_data['away_team']:
                            outcome_type = 'away_win'
                        else:
                            outcome_type = 'unknown'
                        
                        normalized_odds.append({
                            'platform_name': bookmaker['title'],
                            'platform_key': bookmaker['key'],
                            'region': region,
                            'market_type': 'moneyline',
                            'identifier': odds_data.get('id'),  # Use game id as identifier
                            'outcome_name': outcome['name'],
                            'outcome_type': outcome_type,
                            'decimal_odds': float(outcome['price']),
                            'timestamp': datetime.now()
                        })
        
        return normalized_odds