"""MLB team utilities and keyword mappings."""

import re
from typing import List, Dict

# MLB team keywords for matching across platforms
# Organized by priority - longer/more specific terms first to avoid false matches
MLB_TEAM_KEYWORDS = {
    'boston red sox': ['red sox', 'redsox', 'boston red sox', 'boston'],
    'new york yankees': ['new york yankees', 'yankees', 'yanks', 'ny yankees', 'new york y'],
    'tampa bay rays': ['tampa bay rays', 'tampa bay', 'rays'],
    'toronto blue jays': ['toronto blue jays', 'blue jays', 'bluejays', 'toronto'],
    'baltimore orioles': ['baltimore orioles', 'orioles', 'baltimore'],
    'chicago white sox': ['chicago white sox', 'white sox', 'whitesox', 'chicago w', 'chicago ws'],
    'cleveland guardians': ['cleveland guardians', 'guardians', 'cleveland'],
    'detroit tigers': ['detroit tigers', 'tigers', 'detroit'],
    'kansas city royals': ['kansas city royals', 'kansas city', 'royals'],
    'minnesota twins': ['minnesota twins', 'twins', 'minnesota'],
    'houston astros': ['houston astros', 'astros', 'houston'],
    'los angeles angels': ['los angeles angels', 'la angels', 'angels', 'los angeles a'],
    'oakland athletics': ['oakland athletics', 'athletics', 'oakland', "a's"],
    'seattle mariners': ['seattle mariners', 'mariners', 'seattle'],
    'texas rangers': ['texas rangers', 'rangers', 'texas'],
    'atlanta braves': ['atlanta braves', 'braves', 'atlanta'],
    'miami marlins': ['miami marlins', 'marlins', 'miami'],
    'new york mets': ['new york mets', 'ny mets', 'mets', 'new york m'],
    'philadelphia phillies': ['philadelphia phillies', 'phillies', 'philadelphia'],
    'washington nationals': ['washington nationals', 'nationals', 'washington'],
    'chicago cubs': ['chicago cubs', 'cubs', 'chicago c'],
    'cincinnati reds': ['cincinnati reds', 'reds', 'cincinnati'],
    'milwaukee brewers': ['milwaukee brewers', 'brewers', 'milwaukee'],
    'pittsburgh pirates': ['pittsburgh pirates', 'pirates', 'pittsburgh'],
    'st. louis cardinals': ['st. louis cardinals', 'st louis cardinals', 'cardinals', 'st. louis', 'st louis'],
    'arizona diamondbacks': ['arizona diamondbacks', 'diamondbacks', 'arizona', 'dbacks'],
    'colorado rockies': ['colorado rockies', 'rockies', 'colorado'],
    'los angeles dodgers': ['los angeles dodgers', 'la dodgers', 'dodgers', 'los angeles d'],
    'san diego padres': ['san diego padres', 'padres', 'san diego'],
    'san francisco giants': ['san francisco giants', 'sf giants', 'giants', 'san francisco']
}

# Mapping of abbreviations to team names
ABBREVIATION_TO_TEAM = {
    'bos': 'boston red sox',
    'nyy': 'new york yankees', 
    'tb': 'tampa bay rays',
    'tor': 'toronto blue jays',
    'bal': 'baltimore orioles',
    'cws': 'chicago white sox',
    'cle': 'cleveland guardians',
    'det': 'detroit tigers',
    'kc': 'kansas city royals',
    'min': 'minnesota twins',
    'hou': 'houston astros',
    'laa': 'los angeles angels',
    'oak': 'oakland athletics',
    'sea': 'seattle mariners',
    'tex': 'texas rangers',
    'atl': 'atlanta braves',
    'mia': 'miami marlins',
    'nym': 'new york mets',
    'phi': 'philadelphia phillies',
    'was': 'washington nationals',
    'chc': 'chicago cubs',
    'cin': 'cincinnati reds',
    'mil': 'milwaukee brewers',
    'pit': 'pittsburgh pirates',
    'stl': 'st. louis cardinals',
    'ari': 'arizona diamondbacks',
    'col': 'colorado rockies',
    'lad': 'los angeles dodgers',
    'sd': 'san diego padres',
    'sf': 'san francisco giants'
}


def get_team_keywords(team_name: str) -> List[str]:
    """Get keywords for a team name."""
    return MLB_TEAM_KEYWORDS.get(team_name.lower(), [team_name.lower()])


def normalize_team_name_for_matching(team_name: str) -> str:
    """Normalize team name for cross-platform matching as specified in CLAUDE.md."""
    if not team_name:
        return ""
    
    team_lower = team_name.lower().strip()
    
    # Direct lookup in our mapping
    for normalized_name, keywords in MLB_TEAM_KEYWORDS.items():
        if team_lower in keywords or team_lower == normalized_name:
            return normalized_name
    
    # Check abbreviations
    if team_lower in ABBREVIATION_TO_TEAM:
        return ABBREVIATION_TO_TEAM[team_lower]
    
    # Fallback: return normalized input
    return team_lower

def find_teams_in_text(text: str) -> List[str]:
    """Find team names mentioned in text using smart word boundary matching."""
    text_lower = text.lower()
    found_teams = []
    
    # First check for abbreviations with word boundaries
    for abbrev, team_name in ABBREVIATION_TO_TEAM.items():
        # Use word boundaries to match abbreviations exactly
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        if re.search(pattern, text_lower):
            if team_name not in found_teams:
                found_teams.append(team_name)
    
    # Then check for full team names and nicknames
    for normalized_name, keywords in MLB_TEAM_KEYWORDS.items():
        if normalized_name in found_teams:
            continue  # Already found via abbreviation
            
        for keyword in keywords:
            # For longer phrases, use simple substring matching
            # For single words that might cause false positives, use word boundaries
            if len(keyword.split()) > 1 or len(keyword) > 4:
                # Multi-word or long single words - safe to use substring matching
                if keyword in text_lower:
                    if normalized_name not in found_teams:
                        found_teams.append(normalized_name)
                    break
            else:
                # Short single words - use word boundaries to avoid false matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    if normalized_name not in found_teams:
                        found_teams.append(normalized_name)
                    break
    
    return found_teams

def teams_match_fuzzy(team1: str, team2: str) -> bool:
    """Check if two team names refer to the same team using fuzzy matching."""
    if not team1 or not team2:
        return False
    
    # Normalize both teams
    norm1 = normalize_team_name_for_matching(team1)
    norm2 = normalize_team_name_for_matching(team2)
    
    # Direct match
    if norm1 == norm2:
        return True
    
    # Check if either is a keyword of the other
    keywords1 = get_team_keywords(norm1)
    keywords2 = get_team_keywords(norm2)
    
    # Check cross-references
    if team1.lower() in keywords2 or team2.lower() in keywords1:
        return True
    
    return False