"""Odds conversion and de-vigging utilities."""

from typing import List, Dict, Any
import math


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2:
        return round((decimal_odds - 1) * 100)
    else:
        return round(-100 / (decimal_odds - 1))


def decimal_to_implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1 / decimal_odds


def implied_probability_to_decimal(probability: float) -> float:
    """Convert implied probability to decimal odds."""
    return 1 / probability


def devig_odds(outcomes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    De-vig odds using constant exponent method.
    
    Args:
        outcomes: List of dictionaries with 'decimal_odds' key
        
    Returns:
        List with added 'devigged_probability' and 'devigged_decimal_odds' keys
    """
    probabilities = [
        decimal_to_implied_probability(outcome['decimal_odds']) 
        for outcome in outcomes
    ]
    
    total_probability = sum(probabilities)
    
    if total_probability <= 1:
        # No vig detected, return original probabilities
        for i, outcome in enumerate(outcomes):
            outcome['devigged_probability'] = probabilities[i]
            outcome['devigged_decimal_odds'] = outcome['decimal_odds']
        return outcomes
    
    # Find exponent k such that sum(p_i^k) = 1
    # We solve this using binary search
    def sum_powered_probs(k: float) -> float:
        return sum(p ** k for p in probabilities)
    
    # Binary search for the correct exponent
    low, high = 0.0, 1.0
    tolerance = 1e-10
    max_iterations = 100
    
    for _ in range(max_iterations):
        mid = (low + high) / 2
        sum_val = sum_powered_probs(mid)
        
        if abs(sum_val - 1.0) < tolerance:
            break
        elif sum_val > 1.0:
            low = mid
        else:
            high = mid
    
    k = mid
    
    for i, outcome in enumerate(outcomes):
        devigged_prob = probabilities[i] ** k
        outcome['devigged_probability'] = devigged_prob
        outcome['devigged_decimal_odds'] = implied_probability_to_decimal(devigged_prob)
    
    return outcomes