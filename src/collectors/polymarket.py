"""Data collector for Polymarket using Gamma API."""

import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import time
from src.utils.teams import find_teams_in_text, get_team_keywords


class PolymarketCollector:
    def __init__(self):
        self.gamma_url = "https://gamma-api.polymarket.com"
        self.clob_url = "https://clob.polymarket.com"
        self.session = requests.Session()
        
    def _make_gamma_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request to Gamma API with error handling."""
        response = self.session.get(f"{self.gamma_url}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    
    def _make_clob_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request to CLOB API with error handling."""
        response = self.session.get(f"{self.clob_url}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_mlb_events(self) -> List[Dict[str, Any]]:
        """Get MLB events using the Gamma API events endpoint with MLB tag 100381."""
        try:
            # Set end_date_max to 2 weeks in the future as requested
            two_weeks_future = datetime.now() + timedelta(weeks=2)
            end_date_max = two_weeks_future.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            params = {
                "limit": 100,
                "active": True,
                "closed": False,
                "tag_id": "100381",  # MLB tag ID as specified in CLAUDE.md
                "end_date_max": end_date_max  # Limit to 2 weeks in future
            }
            
            data = self._make_gamma_request("events", params)
            
            # Filter for single-game moneyline markets (must have ' vs. ' in title)
            valid_events = []
            
            for event in data:
                title = event.get('title', '')
                
                # Only include events with ' vs. ' in title (single-game markets)
                if ' vs. ' not in title:
                    continue
                
                # Check if event is still active (not ended)
                end_date = event.get('endDate')
                if end_date:
                    try:
                        end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        # Only include future events
                        if end_datetime > datetime.now():
                            valid_events.append(event)
                    except:
                        # If we can't parse date, include it anyway to be safe
                        valid_events.append(event)
                else:
                    valid_events.append(event)
            
            return valid_events
        except Exception as e:
            print(f"Error getting MLB events: {e}")
            return []
    
    def get_event_details(self, event_slug: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific event."""
        try:
            data = self._make_gamma_request(f"events/{event_slug}")
            return data
        except Exception as e:
            print(f"Error fetching event details for {event_slug}: {e}")
            return None
    
    def get_event_markets(self, event_slug: str) -> List[Dict[str, Any]]:
        """Get markets for a specific event."""
        try:
            # Get the event details first to get market info
            event_details = self.get_event_details(event_slug)
            if not event_details:
                return []
            
            markets = event_details.get('markets', [])
            return markets
        except Exception as e:
            print(f"Error fetching markets for event {event_slug}: {e}")
            return []
    
    def get_market_prices(self, condition_id: str, side: str = "buy") -> Optional[Dict[str, Any]]:
        """Get current prices for a market using CLOB API."""
        try:
            # Use CLOB API for pricing data with correct parameters
            params = {
                "token_id": condition_id,
                "side": side
            }
            data = self._make_clob_request("price", params)
            return data
        except Exception as e:
            print(f"Error fetching prices for condition {condition_id}: {e}")
            return None
    
    def extract_game_info_from_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract game information from Polymarket event using title and market data as specified."""
        
        # Use event title field for team names as specified in CLAUDE.md
        title = event_data.get('title', '')
        
        # Find teams mentioned in the title
        found_teams = find_teams_in_text(title)
        
        if len(found_teams) < 2:
            # Also check markets for additional team context
            markets = event_data.get('markets', [])
            for market in markets:
                market_question = market.get('question', '')
                market_teams = find_teams_in_text(market_question)
                for team in market_teams:
                    if team not in found_teams:
                        found_teams.append(team)
                        if len(found_teams) >= 2:
                            break
                if len(found_teams) >= 2:
                    break
        
        if len(found_teams) >= 2:
            # Extract game start time from markets' gameStartTime field as specified
            game_start_time = None
            markets = event_data.get('markets', [])
            for market in markets:
                start_time_str = market.get('gameStartTime')
                if start_time_str:
                    try:
                        # Handle different datetime formats from Polymarket
                        if start_time_str.endswith('+00'):
                            # Fix malformed timezone: '2025-06-19 00:05:00+00' -> '2025-06-19 00:05:00+00:00'
                            start_time_str = start_time_str + ':00'
                        elif 'Z' in start_time_str:
                            # Replace Z with +00:00
                            start_time_str = start_time_str.replace('Z', '+00:00')
                        
                        game_start_time = datetime.fromisoformat(start_time_str)
                        break
                    except Exception as e:
                        print(f"Error parsing game start time {start_time_str}: {e}")
                        continue
            
            if not game_start_time:
                print(f"Warning: No valid game start time found for event {title}")
                return None
            
            return {
                'teams': found_teams[:2],
                'game_start_time': game_start_time,
                'event_title': title
            }
        
        return None
    
    def collect_mlb_events(self) -> List[Dict[str, Any]]:
        """Collect MLB events from Polymarket using the events endpoint as specified."""
        print("Collecting MLB events from Polymarket using Gamma API...")
        
        try:
            mlb_events = self.get_mlb_events()
            
            print(f"Found {len(mlb_events)} MLB events from Polymarket")
            
            # Extract game information from each event
            processed_events = []
            for event in mlb_events:
                # Extract teams and game start time from event title and markets
                game_info = self.extract_game_info_from_event(event)
                if game_info:
                    event['game_info'] = game_info
                    processed_events.append(event)
                    print(f"Processed event: {event.get('title', 'Unknown')} -> {game_info['teams']} at {game_info['game_start_time']}")
                else:
                    print(f"Could not extract game info from: {event.get('title', 'Unknown')}")
            
            print(f"Successfully processed {len(processed_events)} MLB events")
            return processed_events
            
        except Exception as e:
            print(f"Error collecting MLB events: {e}")
            return []
    
    def normalize_market_data(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Polymarket market data to standard format."""
        # Extract team names and game info from question/description
        question = market_data.get('question', '')
        description = market_data.get('description', '')
        
        return {
            'platform_market_id': market_data['id'],
            'market_name': question,
            'market_description': description,
            'market_slug': market_data.get('slug', ''),
            'end_date': market_data.get('endDate'),
            'sport': 'mlb',
            'league': 'Major League Baseball',
            'platform': 'polymarket'
        }
    
    def normalize_odds_data(self, event_data: Dict[str, Any], market_data: Dict[str, Any], price_data: Dict[str, Any], token_index: int = 0) -> List[Dict[str, Any]]:
        """Normalize Polymarket odds data to standard format."""
        normalized_odds = []
        
        # Get team info to determine home/away
        game_info = event_data.get('game_info', {})
        teams = game_info.get('teams', [])
        
        # CLOB API returns different structure - look for current price
        # Price data might have 'mid' price or bid/ask prices
        price = None
        
        if 'mid' in price_data:
            price = float(price_data['mid'])
        elif 'price' in price_data:
            price = float(price_data['price'])
        elif 'last' in price_data:
            price = float(price_data['last'])
        
        if price and 0 < price <= 1:
            # For binary markets, token_index 0 is "Yes", token_index 1 is "No"
            is_yes_outcome = token_index == 0
            
            # Get the actual outcome name from the outcomes field
            outcome_name_from_market = None
            try:
                outcomes_str = market_data.get('outcomes')
                if outcomes_str:
                    outcomes = json.loads(outcomes_str)
                    if outcomes and token_index < len(outcomes):
                        outcome_name_from_market = outcomes[token_index]
            except (json.JSONDecodeError, IndexError, TypeError):
                pass
            
            if is_yes_outcome:
                # Yes outcome - use the price as-is
                decimal_odds = 1 / price if price > 0 else 0
                outcome_type = self._determine_outcome_type_from_market(market_data, teams, token_index)
                outcome_name = outcome_name_from_market or f"Yes - {market_data.get('question', market_data.get('description', ''))}"
                probability = price
            else:
                # No outcome - calculate implied probability of the opposite
                no_probability = 1 - price
                decimal_odds = 1 / no_probability if no_probability > 0 else 0
                # For No outcome, get the opposite of the Yes outcome (token_index 0)
                yes_outcome_type = self._determine_outcome_type_from_market(market_data, teams, 0)
                outcome_type = self._get_opposite_outcome_type(yes_outcome_type)
                outcome_name = f"No - {outcome_name_from_market or market_data.get('question', market_data.get('description', ''))}"
                probability = no_probability
            
            normalized_odds.append({
                'platform_name': 'Polymarket',
                'platform_key': 'polymarket',
                'market_type': 'prediction',
                'identifier': event_data.get('slug'),  # Use event slug as identifier
                'outcome_name': outcome_name,
                'outcome_type': outcome_type,
                'decimal_odds': decimal_odds,
                'probability': probability,
                'timestamp': datetime.now()
            })
        
        return normalized_odds
    
    def _determine_outcome_type_from_market(self, market_data: Dict[str, Any], teams: List[str], token_index: int) -> str:
        """Determine outcome type using the market's outcomes field and token index."""
        
        # Get the outcomes from the market data
        outcomes_str = market_data.get('outcomes')
        if not outcomes_str:
            return 'unknown'
        
        try:
            outcomes = json.loads(outcomes_str)
            if not outcomes or token_index >= len(outcomes):
                return 'unknown'
            
            # Get the outcome name for this token index
            outcome_name = outcomes[token_index]
            
            # Match outcome name to teams to determine home/away
            if len(teams) == 2:
                # Check if outcome name matches home team (teams[0]) or away team (teams[1])
                home_team, away_team = teams[0], teams[1]
                
                # Simple string matching - check if team name is in outcome
                if any(keyword.lower() in outcome_name.lower() for keyword in get_team_keywords(home_team)):
                    return 'home_win'
                elif any(keyword.lower() in outcome_name.lower() for keyword in get_team_keywords(away_team)):
                    return 'away_win'
            
            return 'unknown'
            
        except (json.JSONDecodeError, IndexError, TypeError) as e:
            print(f"Error parsing outcomes for market: {e}")
            return 'unknown'
    
    
    def _get_opposite_outcome_type(self, outcome_type: str) -> str:
        """Get the opposite outcome type."""
        if outcome_type == 'home_win':
            return 'away_win'
        elif outcome_type == 'away_win':
            return 'home_win'
        else:
            return 'unknown'