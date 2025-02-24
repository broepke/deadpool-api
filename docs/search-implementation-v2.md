# Search Implementation Plan V2

## Overview
Implement a flexible search endpoint that initially supports searching people by name, with the architecture designed to support additional entity types in the future. The implementation will leverage existing name matching utilities and optimize DynamoDB access patterns.

## Database Enhancements

### 1. Global Secondary Index for Name-Based Search
Add a GSI to optimize name-based searches:

```
GSI: NameSearchIndex
- PK: Type (e.g., "PERSON", "PLAYER")
- SK: NormalizedName (lowercase, no punctuation)
```

This allows efficient querying by entity type and normalized name prefix.

### 2. Data Migration
1. Add normalized name field to existing records
2. Create migration script to populate the GSI
3. Update entity creation/update logic to maintain normalized names

## API Design

### Search Endpoint
```
GET /api/v1/deadpool/search
```

Query Parameters:
- `q`: Search query string (required)
- `type`: Entity type to search (optional, defaults to "people")
- `mode`: Search mode (optional, "exact" or "fuzzy", defaults to "fuzzy")
- `limit`: Maximum number of results (optional, default 10)
- `offset`: Pagination offset (optional, default 0)

Example Requests:
```
GET /search?q=john&type=people&mode=fuzzy
GET /search?q=smith&type=people&limit=20&offset=0
```

### Response Format
```json
{
  "message": "Successfully retrieved search results",
  "data": [
    {
      "id": "string",
      "type": "people",
      "attributes": {
        "name": "string",
        "status": "alive|deceased",
        "metadata": {}
      },
      "score": 0.95  // Match confidence score
    }
  ],
  "metadata": {
    "total": 100,    // Total matches
    "limit": 10,     // Results per page
    "offset": 0,     // Current offset
    "query": "john"  // Original search query
  }
}
```

## Technical Implementation

### 1. Search Service
Create a new `SearchService` class in `src/services/search.py`:

```python
class SearchService:
    def __init__(self, db_client: DynamoDBClient):
        self.db = db_client
        self.name_matcher = NameMatcher()  # Wrapper for name_matching utilities

    async def search_entities(
        self,
        query: str,
        entity_type: str = "people",
        mode: str = "fuzzy",
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for entities by name.
        Uses GSI for initial filtering, then applies name matching logic.
        """
        normalized_query = normalize_name(query)
        
        # Get candidates from GSI
        candidates = await self._get_search_candidates(
            normalized_query,
            entity_type
        )
        
        # Apply name matching
        matches = self._apply_name_matching(
            query,
            candidates,
            mode
        )
        
        # Sort by score and paginate
        results = self._paginate_results(
            matches,
            limit,
            offset
        )
        
        return {
            "data": results,
            "metadata": {
                "total": len(matches),
                "limit": limit,
                "offset": offset,
                "query": query
            }
        }

    async def _get_search_candidates(
        self,
        normalized_query: str,
        entity_type: str
    ) -> List[Dict[str, Any]]:
        """
        Query the GSI to get initial candidates.
        """
        return await self.db.query_name_index(
            entity_type,
            normalized_query
        )

    def _apply_name_matching(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        mode: str
    ) -> List[Dict[str, Any]]:
        """
        Apply name matching logic to candidates.
        Returns list of matches with confidence scores.
        """
        matches = []
        for candidate in candidates:
            match_result = names_match(
                query,
                candidate["name"],
                fuzzy=(mode == "fuzzy")
            )
            if match_result["match"]:
                matches.append({
                    **candidate,
                    "score": match_result["similarity"]
                })
        return matches

    def _paginate_results(
        self,
        matches: List[Dict[str, Any]],
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """
        Sort matches by score and apply pagination.
        """
        sorted_matches = sorted(
            matches,
            key=lambda x: x["score"],
            reverse=True
        )
        return sorted_matches[offset:offset + limit]
```

### 2. DynamoDB Client Extension
Add methods to `DynamoDBClient` for GSI access:

```python
async def query_name_index(
    self,
    entity_type: str,
    normalized_name_prefix: str
) -> List[Dict[str, Any]]:
    """
    Query the name search GSI.
    """
    response = await self.table.query(
        IndexName="NameSearchIndex",
        KeyConditionExpression=(
            "#type = :type AND begins_with(#name, :prefix)"
        ),
        ExpressionAttributeNames={
            "#type": "Type",
            "#name": "NormalizedName"
        },
        ExpressionAttributeValues={
            ":type": entity_type,
            ":prefix": normalized_name_prefix
        }
    )
    return response["Items"]
```

### 3. FastAPI Router Extension
Add search endpoint to the router:

```python
@router.get("/search", response_model=SearchResponse)
async def search_entities(
    q: str = Query(..., description="Search query string"),
    type: str = Query("people", description="Entity type to search"),
    mode: str = Query("fuzzy", description="Search mode (exact or fuzzy)"),
    limit: int = Query(10, description="Maximum number of results"),
    offset: int = Query(0, description="Pagination offset"),
):
    """
    Search for entities by name.
    Supports fuzzy matching and pagination.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "SEARCH_START",
                "Starting entity search",
                data={
                    "query": q,
                    "type": type,
                    "mode": mode,
                    "limit": limit,
                    "offset": offset
                }
            )

            search_service = SearchService(DynamoDBClient())
            results = await search_service.search_entities(
                q, type, mode, limit, offset
            )

            cwlogger.info(
                "SEARCH_COMPLETE",
                "Search completed successfully",
                data={
                    "query": q,
                    "results_count": len(results["data"]),
                    "total_matches": results["metadata"]["total"],
                    "elapsed_ms": timer.elapsed_ms
                }
            )

            return {
                "message": "Successfully retrieved search results",
                **results
            }

        except Exception as e:
            cwlogger.error(
                "SEARCH_ERROR",
                "Error performing search",
                error=e,
                data={
                    "query": q,
                    "type": type,
                    "elapsed_ms": timer.elapsed_ms
                }
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while performing the search"
            )
```

## Implementation Phases

### Phase 1: Core Implementation
1. Create GSI for name-based searches
2. Implement SearchService with basic functionality
3. Add search endpoint to API
4. Write core tests

### Phase 2: Enhancements
1. Add support for exact/fuzzy mode
2. Implement proper pagination
3. Add result scoring
4. Enhance error handling

### Phase 3: Optimization
1. Add caching layer for frequent searches
2. Optimize GSI usage patterns
3. Add performance monitoring
4. Implement search analytics

## Future Considerations

### 1. Additional Entity Types
- Design allows easy addition of new searchable entities
- Each entity type can implement custom search logic
- Maintain consistent API interface

### 2. Search Enhancements
- Advanced filtering
- Field-specific searches
- Phonetic matching
- Typo tolerance
- Result highlighting

### 3. Performance Optimization
- Caching frequently searched queries
- Implementing cursor-based pagination
- Adding relevant DynamoDB indexes
- Query optimization based on usage patterns

### 4. Monitoring and Analytics
- Track search patterns
- Monitor performance metrics
- Analyze failed searches
- Improve search accuracy based on usage data