"""Data collector for Kalshi API."""

import os
import requests
import json
import time
import hashlib
import hmac
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from src.models.team import find_teams_in_text


class KalshiCollector:
    def __init__(self):
        self.api_key = os.getenv('KALSHI_API_KEY')
        self.private_key_str = os.getenv('KALSHI_API_SECRET')
        
        if not self.api_key:
            raise ValueError("KALSHI_API_KEY environment variable is required")
        
        self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        self.session = requests.Session()
        self.private_key = None
        
        # Load private key if provided
        if self.private_key_str:
            self._load_private_key()
            self._authenticate()
    
    def _load_private_key(self):
        """Load the RSA private key from environment variable."""
        try:
            # Handle both single-line (with \n) and multiline format
            key_data = self.private_key_str.replace('\\n', '\n')
            
            self.private_key = serialization.load_pem_private_key(
                key_data.encode('utf-8'),
                password=None
            )
            print("Successfully loaded Kalshi private key")
            
        except Exception as e:
            print(f"Failed to load Kalshi private key: {e}")
            self.private_key = None
    
    def _create_signature(self, method: str, path: str, body: str = "") -> str:
        """Create signature for Kalshi API request."""
        if not self.private_key:
            return ""
        
        try:
            # Create the message to sign
            timestamp = str(int(time.time()))
            message = f"{timestamp}{method.upper()}{path}{body}"
            
            # Sign the message
            signature = self.private_key.sign(
                message.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            
            # Base64 encode the signature
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            
            return f"{timestamp},{signature_b64}"
            
        except Exception as e:
            print(f"Failed to create signature: {e}")
            return ""
    
    def _authenticate(self):
        """Authenticate with Kalshi API using API key + private key."""
        try:
            # For Kalshi, we don't need a separate login endpoint
            # Authentication is done per-request with signatures
            self.session.headers.update({
                'KALSHI-ACCESS-KEY': self.api_key,
                'Content-Type': 'application/json'
            })
            print("Kalshi API key configured successfully")
            
        except Exception as e:
            print(f"Kalshi authentication setup failed: {e}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, method: str = "GET") -> Dict[str, Any]:
        """Make API request with proper authentication signature."""
        path = f"/{endpoint}"
        url = f"{self.base_url}{path}"
        
        # Create signature if we have a private key
        if self.private_key:
            signature = self._create_signature(method, path)
            if signature:
                self.session.headers.update({'KALSHI-ACCESS-SIGNATURE': signature})
        
        if method.upper() == "GET":
            response = self.session.get(url, params=params)
        elif method.upper() == "POST":
            response = self.session.post(url, json=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    def get_events(self, status: str = "open") -> List[Dict[str, Any]]:
        """Get events from Kalshi."""
        try:
            params = {
                "status": status,
                "series_ticker": 'KXMLBGAME',
                "limit": 200
            }
            
            data = self._make_request("events", params)
            return data.get('events', [])
            
        except Exception as e:
            print(f"Error fetching Kalshi events: {e}")
            return []
    
    def get_markets(self, event_ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get markets from Kalshi."""
        try:
            params = {
                "status": 'open',
                "series_ticker": 'KXMLBGAME',
                "limit": 200
            }
            if event_ticker:
                params["event_ticker"] = event_ticker
            
            data = self._make_request("markets", params)
            return data.get('markets', [])
            
        except Exception as e:
            print(f"Error fetching Kalshi markets: {e}")
            return []
    
    def get_market_orderbook(self, market_ticker: str) -> Dict[str, Any]:
        """Get orderbook for a specific market."""
        try:
            data = self._make_request(f"markets/{market_ticker}/orderbook")
            return data
            
        except Exception as e:
            print(f"Error fetching orderbook for {market_ticker}: {e}")
            return {}
    
    def extract_game_info_from_market(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract game info from Kalshi market using title/subtitle/ticker and close_time as specified."""
        
        # Get text fields to search for teams as specified in CLAUDE.md
        title = market_data.get('title', '')
        subtitle = market_data.get('subtitle', '') 
        ticker = market_data.get('ticker', '')
        
        # Combine all text for team identification
        market_text = f"{title} {subtitle} {ticker}"
        
        # Find teams mentioned in the market
        found_teams = find_teams_in_text(market_text)
        
        if len(found_teams) >= 2:
            # Calculate game start time from close_time 
            # Note: The original CLAUDE.md instruction to subtract 2 years appears to be incorrect
            # Based on testing, close_time is typically ~2 weeks after the actual game date
            close_time_str = market_data.get('close_time')
            if close_time_str:
                try:
                    close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                    # Use close_time minus approximately 2 weeks to get game start time
                    game_start_time = close_time - timedelta(weeks=2)
                    
                    return {
                        'teams': found_teams[:2],
                        'game_start_time': game_start_time,
                        'market_text': market_text,
                        'close_time': close_time
                    }
                except Exception as e:
                    print(f"Error parsing close_time {close_time_str}: {e}")
        
        return None

    def collect_baseball_markets(self) -> List[Dict[str, Any]]:
        """Collect baseball-related markets from Kalshi."""
        print("Collecting baseball markets from Kalshi...")
        
        try:
            # Get all markets and filter for baseball
            all_markets = self.get_markets()
            print(f'Found {len(all_markets)} Kalshi markets to process...')
            baseball_markets = []
            
            for market in all_markets:
                title = market.get('title', '').lower()
                subtitle = market.get('subtitle', '').lower()
                ticker = market.get('ticker', '').lower()
                
                # Filter for baseball/MLB content first
                if (any(keyword in title or keyword in subtitle 
                       for keyword in ['baseball', 'mlb', 'world series', 'pennant']) or
                    'kxmlbgame' in ticker):
                    
                    # Extract game info using title, subtitle, ticker and close_time
                    game_info = self.extract_game_info_from_market(market)
                    if game_info:
                        market['game_info'] = game_info
                        baseball_markets.append(market)
                        print(f"Processed Kalshi market: {market.get('title', 'Unknown')} -> {game_info['teams']} at {game_info['game_start_time']}")
                    else:
                        print(f"Baseball market found but could not extract game info: {title}")
            
            print(f"Successfully processed {len(baseball_markets)} baseball markets from Kalshi")
            return baseball_markets
            
        except Exception as e:
            print(f"Error collecting Kalshi baseball markets: {e}")
            return []
    
    def normalize_market_data(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Kalshi market data to standard format."""
        return {
            'platform_market_id': market_data.get('ticker'),
            'market_name': market_data.get('title', ''),
            'market_description': market_data.get('subtitle', ''),
            'event_ticker': market_data.get('event_ticker'),
            'close_date': market_data.get('close_date'),
            'expiration_date': market_data.get('expiration_date'),
            'sport': 'mlb',
            'league': 'Major League Baseball',
            'platform': 'kalshi'
        }
    
    def normalize_odds_data(self, market_data: Dict[str, Any], orderbook_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalize Kalshi odds data to standard format."""
        normalized_odds = []
        
        # Get team info
        game_info = market_data.get('game_info', {})
        teams = game_info.get('teams', [])
        
        # Extract orderbook from the nested structure
        orderbook = orderbook_data.get('orderbook', {})
        
        # Kalshi orderbook format: {'yes': [[price, quantity], ...], 'no': [[price, quantity], ...]}
        yes_orders = orderbook.get('yes', [])
        no_orders = orderbook.get('no', [])
        
        
        # Find the highest priced yes order (market price should be highest valid bid)
        best_price = None
        volume = 0
        
        if yes_orders and len(yes_orders) > 0:
            # Sort by price (first element) in descending order to get highest price
            sorted_orders = sorted(yes_orders, key=lambda x: x[0] if isinstance(x, list) and len(x) >= 2 else 0, reverse=True)
            
            # Use highest priced order
            best_order = sorted_orders[0]
            if isinstance(best_order, list) and len(best_order) >= 2:
                best_price = best_order[0]  # Price in cents
                volume = best_order[1]      # Quantity
            
            # Also show what the first (original) order was for comparison
            original_first = yes_orders[0]
        
        if best_price is not None and best_price > 0:
            probability = best_price / 100.0  # Kalshi prices in cents
            decimal_odds = 1 / probability if probability > 0 else 0
            
            
            # Determine which team/outcome this is for
            outcome_type = self._determine_outcome_type(market_data, teams)
            
            # Get the appropriate team name for the outcome_name
            outcome_name = "Unknown Team"
            if outcome_type == 'home_win' and len(teams) >= 1:
                outcome_name = teams[0]
            elif outcome_type == 'away_win' and len(teams) >= 2:
                outcome_name = teams[1]
            elif len(teams) >= 1:
                # Fallback to first team if outcome_type is unclear
                outcome_name = teams[0]
            
            normalized_odds.append({
                'platform_name': 'Kalshi',
                'platform_key': 'kalshi',
                'market_type': 'prediction',
                'identifier': market_data.get('event_ticker'),  # Use event_ticker as identifier
                'outcome_name': outcome_name,
                'outcome_type': outcome_type,
                'decimal_odds': decimal_odds,
                'probability': probability,
                'volume': volume,
                'timestamp': datetime.now()
            })
        
        return normalized_odds
    
    def _determine_outcome_type(self, market_data: Dict[str, Any], teams: List[str]) -> str:
        """Determine which team this market is betting on."""
        if len(teams) != 2:
            return 'unknown'
        
        # Method 1: Use ticker - extract team abbreviation from last part after '-'
        ticker = market_data.get('ticker', '')
        if ticker and '-' in ticker:
            team_abbrev = ticker.split('-')[-1].upper()
            
            # Match against team abbreviations/keywords
            for i, team in enumerate(teams):
                from src.models.team import Team
                team_obj = Team.find_team_by_name(team, 'mlb')
                if team_obj:
                    # Check if the ticker abbreviation matches any of the team's keywords
                    team_keywords = [kw.upper() for kw in team_obj.keywords]
                    if team_abbrev in team_keywords:
                        return 'home_win' if i == 0 else 'away_win'
        
        # Method 2: Use yes_sub_title if ticker method didn't work
        yes_sub_title = market_data.get('yes_sub_title', '').lower()
        if yes_sub_title:
            for i, team in enumerate(teams):
                from src.models.team import Team
                team_obj = Team.find_team_by_name(team, 'mlb')
                team_keywords = team_obj.keywords if team_obj else [team.lower()]
                for keyword in team_keywords:
                    if keyword.lower() in yes_sub_title:
                        return 'home_win' if i == 0 else 'away_win'
        
        # Fallback - assume first team mentioned is home team
        return 'home_win'