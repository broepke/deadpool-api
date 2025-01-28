# Name Matching Architecture

## Current Implementation

The current name matching implementation in the `/draft` endpoint uses a simple case-insensitive exact match:

```python
existing_person = next(
    (p for p in people if p["name"].lower() == draft_request.name.lower()),
    None,
)
```

This approach has limitations:

- While case-insensitive, it requires exact character matches
- Punctuation differences cause mismatches (e.g., "Donald Trump, Jr." vs "Donald Trump Jr")
- No handling of common name variations or typos

## Proposed Improvements

### 1. Name Normalization

Before comparison, names should be normalized to handle common variations:

1. Case normalization:

   - Convert to lowercase
   - Handle special characters (e.g., é → e)

2. Punctuation normalization:

   - Remove or standardize commas in names
   - Handle periods in abbreviations
   - Standardize spaces around punctuation

3. Format standardization:
   - Normalize suffixes (Jr., Jr, Junior)
   - Handle common title variations (Dr., Dr, Doctor)

### 2. Fuzzy Matching

Implement fuzzy matching to catch small differences:

1. Levenshtein Distance:

   - Calculate edit distance between names
   - Set appropriate threshold (e.g., 2 for short names, proportional for longer names)

2. Token-based comparison:
   - Split names into tokens
   - Compare token sets for partial matches
   - Handle word order variations

### 3. Implementation Approach

```python
def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison:
    1. Convert to lowercase
    2. Remove/standardize punctuation
    3. Handle common variations
    """
    # Convert to lowercase
    name = name.lower()

    # Standardize suffixes
    suffix_map = {
        'jr.': 'jr',
        'sr.': 'sr',
        'junior': 'jr',
        'senior': 'sr'
    }

    # Remove commas, standardize spaces
    name = name.replace(',', ' ').replace('  ', ' ').strip()

    # Apply suffix standardization
    for old, new in suffix_map.items():
        if name.endswith(old):
            name = name[:-len(old)] + new

    return name

def names_match(name1: str, name2: str, threshold: float = 0.85) -> bool:
    """
    Compare two names using fuzzy matching:
    1. Normalize both names
    2. Check for exact match after normalization
    3. Apply fuzzy matching if needed
    """
    # Normalize both names
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    # Check exact match after normalization
    if norm1 == norm2:
        return True

    # Calculate similarity score
    similarity = calculate_similarity(norm1, norm2)
    return similarity >= threshold
```

### 4. Configuration

The matching logic should be configurable to allow tuning:

```python
NAME_MATCHING_CONFIG = {
    'similarity_threshold': 0.85,  # Minimum similarity score to consider a match
    'min_length_for_fuzzy': 4,    # Minimum name length to apply fuzzy matching
    'suffix_map': {               # Standardization mappings
        'jr.': 'jr',
        'sr.': 'sr',
        'junior': 'jr',
        'senior': 'sr'
    }
}
```

## Benefits

1. **Improved Accuracy**: Catches common variations and typos while maintaining precision
2. **Configurability**: Easy to tune matching parameters
3. **Maintainability**: Centralized name matching logic
4. **Extensibility**: Easy to add new normalization rules or matching algorithms

## Considerations

1. **Performance**:

   - Fuzzy matching is more computationally intensive
   - Consider caching normalized names
   - May need optimization for large datasets

2. **False Positives**:

   - Balance between catching variations and avoiding incorrect matches
   - May need manual review process for borderline cases

3. **Internationalization**:
   - Consider Unicode normalization
   - Handle culture-specific name formats
   - Support non-Latin characters

## Implementation Plan

1. Create utility module for name matching
2. Implement normalization functions
3. Add fuzzy matching with configurable thresholds
4. Update draft endpoint to use new matching
5. Add logging for match decisions
6. Create test suite for various name scenarios
