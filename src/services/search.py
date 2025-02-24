"""
Search service for finding entities by name with support for fuzzy matching.
"""
from typing import Dict, List, Any, Optional
from ..utils.name_matching import names_match, normalize_name
from ..utils.dynamodb import DynamoDBClient
from ..utils.logging import cwlogger, Timer

class SearchService:
    """
    Service for searching entities by name.
    Supports fuzzy matching and pagination.
    """
    def __init__(self, db_client: DynamoDBClient):
        self.db = db_client

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
        
        Args:
            query: Search query string
            entity_type: Type of entity to search (e.g., "people", "players")
            mode: Search mode ("exact" or "fuzzy")
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)
            
        Returns:
            Dict containing search results and metadata
        """
        with Timer() as timer:
            try:
                # Normalize query for consistent matching
                normalized_query = normalize_name(query)
                
                # Get all entities of the requested type
                # TODO: Replace with GSI query once implemented
                if entity_type == "people":
                    entities = await self.db.get_people()
                else:
                    raise ValueError(f"Unsupported entity type: {entity_type}")

                cwlogger.info(
                    "SEARCH_SERVICE",
                    f"Retrieved {len(entities)} entities to search",
                    data={
                        "query": query,
                        "entity_type": entity_type,
                        "normalized_query": normalized_query
                    }
                )

                # Apply name matching
                matches = []
                for entity in entities:
                    entity_name = entity["name"]
                    
                    # For exact mode, use full name matching
                    if mode == "exact":
                        match_result = names_match(query, entity_name)
                    else:
                        # For fuzzy mode, check if query matches any part of the name
                        name_parts = entity_name.lower().split()
                        query_parts = normalized_query.split()
                        
                        # Check if any query part matches any name part
                        best_score = 0
                        for q_part in query_parts:
                            for n_part in name_parts:
                                match_result = names_match(q_part, n_part, threshold=0.8)
                                if match_result["match"]:
                                    best_score = max(best_score, match_result["similarity"])
                        
                        match_result = {
                            "match": best_score > 0,
                            "similarity": best_score,
                            "normalized1": normalized_query,
                            "normalized2": entity_name.lower()
                        }
                    
                    cwlogger.debug(
                        "SEARCH_MATCH_ATTEMPT",
                        "Attempted name match",
                        data={
                            "query": query,
                            "entity_name": entity["name"],
                            "match_result": match_result
                        }
                    )
                    
                    if match_result["match"]:
                        # Add match details to entity
                        entity_with_score = {
                            "id": entity["id"],
                            "type": entity_type,
                            "attributes": {
                                "name": entity["name"],
                                "status": "deceased" if entity.get("metadata", {}).get("DeathDate") else "alive",
                                "metadata": entity.get("metadata", {})
                            },
                            "score": match_result["similarity"]
                        }
                        matches.append(entity_with_score)

                # Sort by score descending
                matches.sort(key=lambda x: x["score"], reverse=True)
                
                # Apply pagination
                paginated_matches = matches[offset:offset + limit]

                cwlogger.info(
                    "SEARCH_SERVICE",
                    "Search completed successfully",
                    data={
                        "query": query,
                        "entity_type": entity_type,
                        "mode": mode,
                        "total_matches": len(matches),
                        "returned_matches": len(paginated_matches),
                        "elapsed_ms": timer.elapsed_ms
                    }
                )

                return {
                    "data": paginated_matches,
                    "metadata": {
                        "total": len(matches),
                        "limit": limit,
                        "offset": offset,
                        "query": query
                    }
                }

            except Exception as e:
                cwlogger.error(
                    "SEARCH_SERVICE_ERROR",
                    "Error performing search",
                    error=e,
                    data={
                        "query": query,
                        "entity_type": entity_type,
                        "mode": mode,
                        "elapsed_ms": timer.elapsed_ms
                    }
                )
                raise