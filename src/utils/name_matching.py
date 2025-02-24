"""
Utility module for robust name matching with normalization and fuzzy matching capabilities.
"""
from typing import Dict, Optional, Any
from rapidfuzz.fuzz import ratio

# Configuration for name matching
NAME_MATCHING_CONFIG = {
    'similarity_threshold': 0.85,  # Minimum similarity score to consider a match
    'min_length_for_fuzzy': 4,    # Minimum name length to apply fuzzy matching
    'suffix_map': {               # Standardization mappings
        'jr.': 'jr',
        'sr.': 'sr',
        'junior': 'jr',
        'senior': 'sr',
        'iii': '3',
        'ii': '2'
    }
}

def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison by standardizing case, punctuation, and common variations.
    
    Args:
        name: The name to normalize
        
    Returns:
        Normalized version of the name
    """
    if not name:
        return ""
        
    # Convert to lowercase
    normalized = name.lower()
    
    # Remove/standardize punctuation
    normalized = normalized.replace(',', ' ')  # Remove commas
    normalized = normalized.replace('.', ' ')  # Remove periods
    
    # Standardize multiple spaces
    normalized = ' '.join(normalized.split())
    
    # Handle suffixes
    words = normalized.split()
    if words:
        last_word = words[-1]
        if last_word in NAME_MATCHING_CONFIG['suffix_map']:
            words[-1] = NAME_MATCHING_CONFIG['suffix_map'][last_word]
            normalized = ' '.join(words)
            
    return normalized.strip()

def calculate_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two names using rapidfuzz ratio.
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        
    Returns:
        Similarity score between 0 and 1
    """
    # Handle empty strings
    if not name1 and not name2:
        return 1.0
    if not name1 or not name2:
        return 0.0
        
    return ratio(name1, name2) / 100.0  # Convert rapidfuzz's 0-100 score to 0-1

def get_player_name(player: Dict[str, Any]) -> str:
    """Helper function to get player's full name from FirstName and LastName."""
    return f"{player.get('FirstName', '')} {player.get('LastName', '')}".strip()

def names_match(name1: str, name2: str, threshold: Optional[float] = None) -> Dict:
    """
    Compare two names using normalization and fuzzy matching.
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        threshold: Optional custom similarity threshold (uses config default if not provided)
        
    Returns:
        Dict containing match result and details:
        {
            'match': bool,              # Whether names are considered a match
            'similarity': float,         # Similarity score (0-1)
            'normalized1': str,          # Normalized version of name1
            'normalized2': str,          # Normalized version of name2
            'exact_match': bool         # Whether names matched exactly after normalization
        }
    """
    if threshold is None:
        threshold = NAME_MATCHING_CONFIG['similarity_threshold']
        
    # Normalize both names
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    
    # Check for exact match after normalization
    if norm1 == norm2:
        return {
            'match': True,
            'similarity': 1.0,
            'normalized1': norm1,
            'normalized2': norm2,
            'exact_match': True
        }
    
    # Skip fuzzy matching for very short names
    if len(norm1) < NAME_MATCHING_CONFIG['min_length_for_fuzzy'] or \
       len(norm2) < NAME_MATCHING_CONFIG['min_length_for_fuzzy']:
        return {
            'match': False,
            'similarity': 0.0,
            'normalized1': norm1,
            'normalized2': norm2,
            'exact_match': False
        }
    
    # Calculate similarity score
    similarity = calculate_similarity(norm1, norm2)
    
    return {
        'match': similarity >= threshold,
        'similarity': similarity,
        'normalized1': norm1,
        'normalized2': norm2,
        'exact_match': False
    }