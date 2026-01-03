"""Improved service class for handling picks-related operations with 2026 migration fixes."""
from datetime import datetime
from typing import Any, Dict, Optional
from ..models.deadpool import PickDetail, PicksCountEntry, LeaderboardEntry
from ..utils.dynamodb import DynamoDBClient
from ..utils.caching import reporting_cache, next_drafter_cache
from ..utils.logging import cwlogger


class ImprovedPicksService:
    """Improved service class for handling picks-related operations with 2026 migration fixes."""

    def __init__(self, db_client: DynamoDBClient):
        self.db = db_client

    def _get_safe_year(self, year: Optional[int] = None) -> int:
        """
        Get a safe year parameter with fallback logic for 2026 migration issues.
        
        Args:
            year: Optional year parameter
            
        Returns:
            Safe year to use for queries
        """
        if year is not None:
            return year
        
        current_year = datetime.now().year
        
        # If current year is 2026, check if we have proper 2026 data
        if current_year == 2026:
            try:
                # Quick check if 2026 draft order exists
                response = self.db.table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={':pk': 'YEAR#2026'},
                    Limit=1
                )
                
                if not response.get('Items'):
                    cwlogger.warning(
                        "YEAR_FALLBACK",
                        "No 2026 draft order found, falling back to 2025",
                        data={"requested_year": current_year, "fallback_year": 2025}
                    )
                    return 2025
                    
            except Exception as e:
                cwlogger.error(
                    "YEAR_CHECK_ERROR",
                    "Error checking 2026 data availability",
                    error=e,
                    data={"requested_year": current_year}
                )
                return 2025
        
        return current_year

    async def get_picks_by_person(
        self,
        person_id: str,
        year: Optional[int] = None,
        limit: Optional[int] = None,
        page: Optional[int] = 1,
        page_size: Optional[int] = 10
    ) -> Dict[str, Any]:
        """
        Get picks for a specific person with improved error handling and year fallback.
        
        Args:
            person_id: ID of the person to get picks for
            year: Optional year filter
            limit: Optional limit on results
            page: Page number for pagination
            page_size: Number of items per page
            
        Returns:
            Dictionary containing picks data and pagination info
        """
        try:
            # Use safe year logic
            target_year = self._get_safe_year(year)
            
            cwlogger.info(
                "GET_PICKS_BY_PERSON_START",
                f"Retrieving picks for person {person_id}",
                data={
                    "person_id": person_id,
                    "requested_year": year,
                    "target_year": target_year,
                    "limit": limit,
                    "page": page,
                    "page_size": page_size
                }
            )
            
            # First check if the person exists
            person = await self.db.get_person(person_id)
            if not person:
                cwlogger.warning(
                    "GET_PICKS_BY_PERSON_ERROR",
                    "Person not found",
                    data={"person_id": person_id}
                )
                return {
                    "message": "Person not found",
                    "data": [],
                    "total": 0,
                    "page": page if limit is None else 1,
                    "page_size": limit or page_size,
                    "total_pages": 0
                }
            
            # Determine years to search
            if year is not None:
                years_to_search = [year]
            else:
                # Search multiple years but prioritize the target year
                years_to_search = [target_year]
                # Add previous years if target year is current year
                if target_year == datetime.now().year:
                    years_to_search.extend([target_year - 1, target_year - 2])
            
            # Get all picks for this person across the specified years
            all_picks = []
            unique_picks = set()  # Track unique player-person-year combinations
            
            for search_year in years_to_search:
                try:
                    # Get players for this year
                    players = await self.db.get_players(search_year)
                    if not players:
                        cwlogger.info(
                            "GET_PICKS_BY_PERSON_INFO",
                            f"No players found for year {search_year}",
                            data={"year": search_year, "person_id": person_id}
                        )
                        continue
                    
                    # Check each player's picks for this person
                    for player in players:
                        player_id = player["id"]
                        player_picks = await self.db.get_player_picks(player_id, search_year)
                        
                        for pick in player_picks:
                            # Check if this pick is for the requested person
                            if pick["person_id"] == person_id:
                                # Create a unique key for this player-person-year combination
                                unique_key = f"{player_id}_{person_id}_{pick['year']}"
                                
                                # Only add if we haven't seen this combination before
                                if unique_key not in unique_picks:
                                    unique_picks.add(unique_key)
                                    
                                    pick_detail = PickDetail(
                                        player_id=player_id,
                                        player_name=player["name"],
                                        draft_order=player["draft_order"],
                                        pick_person_id=person_id,
                                        pick_person_name=person["name"],
                                        pick_person_age=person["metadata"].get("Age"),
                                        pick_person_birth_date=person["metadata"].get("BirthDate"),
                                        pick_person_death_date=person["metadata"].get("DeathDate"),
                                        pick_timestamp=pick["timestamp"],
                                        year=pick["year"],
                                    )
                                    all_picks.append(pick_detail)
                
                except Exception as e:
                    cwlogger.error(
                        "GET_PICKS_BY_PERSON_YEAR_ERROR",
                        f"Error getting picks for year {search_year}",
                        error=e,
                        data={"year": search_year, "person_id": person_id}
                    )
                    # Continue with other years
                    continue
            
            # Sort by timestamp descending
            all_picks.sort(key=lambda x: x.pick_timestamp or "", reverse=True)
            
            total_items = len(all_picks)
            
            cwlogger.info(
                "GET_PICKS_BY_PERSON_COMPLETE",
                f"Retrieved {total_items} picks for person {person_id}",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "target_year": target_year,
                    "years_searched": years_to_search,
                    "total_picks": total_items
                }
            )
            
            # Handle limit case
            if limit is not None:
                limited_picks = all_picks[:limit]
                return {
                    "message": "Successfully retrieved picks",
                    "data": limited_picks,
                    "total": total_items,
                    "page": 1,
                    "page_size": limit,
                    "total_pages": 1
                }
            
            # Handle pagination case
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_picks = all_picks[start_idx:end_idx]
            total_pages = (total_items + page_size - 1) // page_size
            
            return {
                "message": "Successfully retrieved picks",
                "data": paginated_picks,
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
        except Exception as e:
            cwlogger.error(
                "GET_PICKS_BY_PERSON_ERROR",
                f"Error retrieving picks for person {person_id}",
                error=e,
                data={
                    "person_id": person_id,
                    "year": year,
                    "target_year": target_year if 'target_year' in locals() else None
                }
            )
            return {
                "message": "Error retrieving picks",
                "data": [],
                "total": 0,
                "page": page if limit is None else 1,
                "page_size": limit or page_size,
                "total_pages": 0
            }

    async def get_picks(
        self,
        year: Optional[int] = None,
        limit: Optional[int] = None,
        page: Optional[int] = 1,
        page_size: Optional[int] = 10,
    ) -> Dict:
        """
        Get all picks for a given year with improved error handling.
        """
        target_year = self._get_safe_year(year)
        
        # Include pagination parameters in the cache key
        if limit is not None:
            cache_key = f"picks_list_{target_year}_limit_{limit}"
        else:
            cache_key = f"picks_list_{target_year}_page_{page}_size_{page_size}"

        return await reporting_cache.get_or_compute(
            cache_key,
            lambda: self._compute_picks_list(target_year, limit, page, page_size)
        )

    async def _compute_picks_list(
        self,
        target_year: int,
        limit: Optional[int] = None,
        page: Optional[int] = 1,
        page_size: Optional[int] = 10,
    ) -> Dict:
        """Compute picks list with improved error handling."""
        try:
            # Get all players for the year
            players = await self.db.get_players(target_year)
            if not players:
                cwlogger.warning(
                    "COMPUTE_PICKS_LIST_WARNING",
                    f"No players found for year {target_year}",
                    data={"year": target_year}
                )
                return self._empty_picks_response(target_year, limit, page, page_size)

            # Batch get all picks for all players
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all unique person IDs
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            # Build detailed picks list
            detailed_picks = []
            for player in players:
                picks = all_picks.get(player["id"], [])
                if picks:
                    # Add picks with details
                    for pick in picks:
                        person = people.get(pick["person_id"])
                        if person:
                            person_metadata = person.get("metadata", {})
                            pick_detail = PickDetail(
                                player_id=player["id"],
                                player_name=player["name"],
                                draft_order=player["draft_order"],
                                pick_person_id=pick["person_id"],
                                pick_person_name=person["name"],
                                pick_person_age=person_metadata.get("Age"),
                                pick_person_birth_date=person_metadata.get("BirthDate"),
                                pick_person_death_date=person_metadata.get("DeathDate"),
                                pick_timestamp=pick["timestamp"],
                                year=target_year,
                            )
                            detailed_picks.append(pick_detail)
                else:
                    # Include player with no picks
                    pick_detail = PickDetail(
                        player_id=player["id"],
                        player_name=player["name"],
                        draft_order=player["draft_order"],
                        pick_person_id=None,
                        pick_person_name=None,
                        pick_person_age=None,
                        pick_person_birth_date=None,
                        pick_person_death_date=None,
                        pick_timestamp=None,
                        year=target_year,
                    )
                    detailed_picks.append(pick_detail)

            # Sort by timestamp descending (None values last), then by draft order
            detailed_picks.sort(
                key=lambda x: (
                    x.pick_timestamp is None,
                    x.pick_timestamp or "",
                    x.draft_order
                ),
                reverse=True
            )

            total_items = len(detailed_picks)

            # Handle limit case
            if limit is not None:
                return {
                    "message": "Successfully retrieved picks",
                    "data": detailed_picks[:limit],
                    "total": total_items,
                    "page": 1,
                    "page_size": limit,
                    "total_pages": 1
                }

            # Handle pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_picks = detailed_picks[start_idx:end_idx]
            total_pages = (total_items + page_size - 1) // page_size

            return {
                "message": "Successfully retrieved picks",
                "data": paginated_picks,
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }

        except Exception as e:
            cwlogger.error(
                "COMPUTE_PICKS_LIST_ERROR",
                f"Error computing picks list for year {target_year}",
                error=e,
                data={"year": target_year}
            )
            raise Exception(f"Error computing picks list: {str(e)}")

    def _empty_picks_response(
        self,
        year: int,
        limit: Optional[int] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict:
        """Return empty picks response structure."""
        return {
            "message": "Successfully retrieved picks",
            "data": [],
            "total": 0,
            "page": page if limit is None else 1,
            "page_size": limit or page_size,
            "total_pages": 0
        }