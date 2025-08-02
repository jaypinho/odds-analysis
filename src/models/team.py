"""Team model for database operations."""

import re
from typing import List, Dict, Optional, Tuple
from src.config.database import db_manager


class Team:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.canonical_name = kwargs.get('canonical_name')
        self.sport = kwargs.get('sport')
        self.league = kwargs.get('league')
        self.abbreviation = kwargs.get('abbreviation')
        self.keywords = kwargs.get('keywords', [])
        self.city = kwargs.get('city')
        self.nickname = kwargs.get('nickname')
        self.timezone = kwargs.get('timezone')
    
    @classmethod
    def find_team_by_name(cls, team_name: str, sport: str = 'mlb') -> Optional['Team']:
        """Find a team by matching against canonical name, abbreviation, or keywords."""
        if not team_name:
            return None
        
        team_lower = team_name.lower().strip()
        
        # Try exact match on canonical name first
        query = """
            SELECT * FROM teams 
            WHERE sport = %s AND LOWER(canonical_name) = %s
        """
        result = db_manager.execute_query(query, (sport, team_lower))
        if result:
            return cls._create_from_row(result[0])
        
        # Try abbreviation match
        query = """
            SELECT * FROM teams 
            WHERE sport = %s AND LOWER(abbreviation) = %s
        """
        result = db_manager.execute_query(query, (sport, team_lower))
        if result:
            return cls._create_from_row(result[0])
        
        # Try keywords match using PostgreSQL array operators
        query = """
            SELECT * FROM teams 
            WHERE sport = %s AND %s = ANY(keywords)
        """
        result = db_manager.execute_query(query, (sport, team_lower))
        if result:
            return cls._create_from_row(result[0])
        
        # Try partial matches in keywords (for cases where input might be slightly different)
        query = """
            SELECT *, 
                   CASE 
                       WHEN %s = ANY(keywords) THEN 1
                       WHEN EXISTS (
                           SELECT 1 FROM unnest(keywords) AS kw 
                           WHERE kw ILIKE %s
                       ) THEN 2
                       ELSE 3
                   END as match_priority
            FROM teams 
            WHERE sport = %s 
            AND EXISTS (
                SELECT 1 FROM unnest(keywords) AS kw 
                WHERE kw ILIKE %s OR %s ILIKE ('%%' || kw || '%%')
            )
            ORDER BY match_priority ASC
            LIMIT 1
        """
        like_pattern = f'%{team_lower}%'
        result = db_manager.execute_query(query, (
            team_lower, like_pattern, sport, like_pattern, team_lower
        ))
        if result:
            return cls._create_from_row(result[0][:-1])  # Exclude match_priority column
        
        return None
    
    @classmethod
    def find_teams_in_text(cls, text: str, sport: str = 'mlb') -> List['Team']:
        """Find team names mentioned in text using smart matching."""
        text_lower = text.lower()
        found_teams = []
        
        # Get all teams for the sport
        query = "SELECT * FROM teams WHERE sport = %s ORDER BY LENGTH(canonical_name) DESC"
        results = db_manager.execute_query(query, (sport,))
        
        if not results:
            return found_teams
        
        teams = [cls._create_from_row(row) for row in results]
        
        # First check for abbreviations with word boundaries
        for team in teams:
            if team.abbreviation:
                pattern = r'\b' + re.escape(team.abbreviation.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    if team not in found_teams:
                        found_teams.append(team)
        
        # Then check for keywords and names
        for team in teams:
            if team in found_teams:
                continue  # Already found via abbreviation
            
            # Check canonical name
            if team.canonical_name.lower() in text_lower:
                found_teams.append(team)
                continue
            
            # Check keywords
            for keyword in team.keywords:
                if len(keyword.split()) > 1 or len(keyword) > 4:
                    # Multi-word or long single words - safe to use substring matching
                    if keyword in text_lower:
                        found_teams.append(team)
                        break
                else:
                    # Short single words - use word boundaries to avoid false matches
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, text_lower):
                        found_teams.append(team)
                        break
        
        return found_teams
    
    @classmethod
    def get_team_by_id(cls, team_id: int) -> Optional['Team']:
        """Get team by ID."""
        query = "SELECT * FROM teams WHERE id = %s"
        result = db_manager.execute_query(query, (team_id,))
        if result:
            return cls._create_from_row(result[0])
        return None
    
    @classmethod
    def get_all_teams(cls, sport: str = 'mlb') -> List['Team']:
        """Get all teams for a sport."""
        query = "SELECT * FROM teams WHERE sport = %s ORDER BY canonical_name"
        results = db_manager.execute_query(query, (sport,))
        return [cls._create_from_row(row) for row in results] if results else []
    
    @classmethod
    def _create_from_row(cls, row) -> 'Team':
        """Create Team instance from database row."""
        return cls(**dict(zip([
            'id', 'canonical_name', 'sport', 'league', 'abbreviation', 
            'keywords', 'city', 'nickname', 'timezone', 'created_at', 'updated_at'
        ], row)))
    
    def __eq__(self, other):
        if not isinstance(other, Team):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)
    
    def __repr__(self):
        return f"Team(id={self.id}, canonical_name='{self.canonical_name}')"


def normalize_team_name_for_matching(team_name: str, sport: str = 'mlb') -> Optional[str]:
    """
    Normalize team name for cross-platform matching using the database.
    Returns the canonical team name if found, None otherwise.
    """
    team = Team.find_team_by_name(team_name, sport)
    return team.canonical_name if team else None


def find_teams_in_text(text: str, sport: str = 'mlb') -> List[str]:
    """
    Find team names mentioned in text.
    Returns list of canonical team names.
    """
    teams = Team.find_teams_in_text(text, sport)
    return [team.canonical_name for team in teams]


def teams_match_fuzzy(team1: str, team2: str, sport: str = 'mlb') -> bool:
    """Check if two team names refer to the same team using fuzzy matching."""
    if not team1 or not team2:
        return False
    
    # Find both teams in database
    team1_obj = Team.find_team_by_name(team1, sport)
    team2_obj = Team.find_team_by_name(team2, sport)
    
    # If both found, check if they're the same team
    if team1_obj and team2_obj:
        return team1_obj.id == team2_obj.id
    
    # If only one found, check if the other name matches any keywords of the found team
    if team1_obj:
        return team2.lower().strip() in team1_obj.keywords
    elif team2_obj:
        return team1.lower().strip() in team2_obj.keywords
    
    return False