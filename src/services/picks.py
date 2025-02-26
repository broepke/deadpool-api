"""Service class for handling picks-related operations."""
from datetime import datetime
from typing import Any, Dict, Optional
from ..models.deadpool import PickDetail, PicksCountEntry
from ..utils.dynamodb import DynamoDBClient
from ..utils.caching import reporting_cache, next_drafter_cache


class PicksService:
    """Service class for handling picks-related operations."""

    def __init__(self, db_client: DynamoDBClient):
        self.db = db_client

    async def get_picks(
        self,
        year: Optional[int] = None,
        limit: Optional[int] = None,
        page: Optional[int] = 1,
        page_size: Optional[int] = 10,
    ) -> Dict:
        """
        Get all picks for a given year with optimized batch operations.
        Uses caching to improve performance.
        """
        target_year = year if year else datetime.now().year
        
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
        """Compute picks list with optimized batch operations."""
        try:
            # Get all players for the year
            players = await self.db.get_players(target_year)
            if not players:
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

    async def get_picks_counts(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Get pick counts for all players with optimized batch operations."""
        target_year = year if year else datetime.now().year
        cache_key = f"picks_counts_{target_year}"

        return await reporting_cache.get_or_compute(
            cache_key,
            lambda: self._compute_picks_counts(target_year)
        )

    async def _compute_picks_counts(self, target_year: int) -> Dict[str, Any]:
        """Compute pick counts with optimized batch operations."""
        try:
            # Get all players for the year
            players = await self.db.get_players(target_year)
            if not players:
                return {"message": "Successfully retrieved pick counts", "data": []}

            # Batch get all picks for all players
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all unique person IDs
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            # Calculate pick counts for each player
            picks_counts = []
            for player in players:
                picks = all_picks.get(player["id"], [])
                
                # Count only picks for people who are alive
                alive_pick_count = 0
                for pick in picks:
                    person = people.get(pick["person_id"])
                    if person and "DeathDate" not in person.get("metadata", {}):
                        alive_pick_count += 1

                picks_count_entry = PicksCountEntry(
                    player_id=player["id"],
                    player_name=player["name"],
                    draft_order=player["draft_order"],
                    pick_count=alive_pick_count,
                    year=target_year,
                )
                picks_counts.append(picks_count_entry)

            # Sort by draft order
            picks_counts.sort(key=lambda x: x.draft_order)

            return {
                "message": "Successfully retrieved pick counts",
                "data": picks_counts,
            }

        except Exception as e:
            raise Exception(f"Error computing picks counts: {str(e)}")

    async def get_next_drafter(self) -> Dict[str, Any]:
        """Get the next player who should draft with optimized batch operations."""
        target_year = datetime.now().year
        cache_key = f"next_drafter_{target_year}"

        # Using next_drafter_cache which has a 30 second TTL
        return await next_drafter_cache.get_or_compute(
            cache_key,
            lambda: self._compute_next_drafter(target_year)
        )

    async def _compute_next_drafter(self, target_year: int) -> Dict[str, Any]:
        """Compute next drafter with optimized batch operations."""
        try:
            # Get all players for the year
            players = await self.db.get_players(target_year)
            if not players:
                return {
                    "message": "No eligible players found",
                    "data": {
                        "player_id": "",
                        "player_name": "",
                        "draft_order": 0,
                        "current_pick_count": 0,
                        "active_pick_count": 0
                    }
                }

            # Batch get all picks for all players
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all unique person IDs
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            # Calculate pick counts for each player
            player_data = []
            for player in players:
                picks = all_picks.get(player["id"], [])

                # Count picks for active people only
                active_pick_count = 0
                for pick in picks:
                    person = people.get(pick["person_id"])
                    if person and "DeathDate" not in person.get("metadata", {}):
                        active_pick_count += 1

                # Only include players who haven't reached 20 active picks
                if active_pick_count < 20:
                    player_data.append({
                        "id": player["id"],
                        "name": player["name"],
                        "draft_order": player["draft_order"],
                        "pick_count": len(picks),
                        "active_pick_count": active_pick_count,
                    })

            if not player_data:
                return {
                    "message": "No eligible players found",
                    "data": {
                        "player_id": "",
                        "player_name": "",
                        "draft_order": 0,
                        "current_pick_count": 0,
                        "active_pick_count": 0
                    }
                }

            # Sort by pick count first, then by draft order
            player_data.sort(key=lambda x: (x["pick_count"], x["draft_order"]))

            # Return the first player (lowest pick count and draft order)
            next_drafter = player_data[0]

            return {
                "message": "Successfully determined next drafter",
                "data": {
                    "player_id": next_drafter["id"],
                    "player_name": next_drafter["name"],
                    "draft_order": next_drafter["draft_order"],
                    "current_pick_count": next_drafter["pick_count"],
                    "active_pick_count": next_drafter["active_pick_count"],
                }
            }

        except Exception as e:
            raise Exception(f"Error computing next drafter: {str(e)}")

    async def invalidate_picks_cache(self, year: Optional[int] = None) -> None:
        """Invalidate all picks-related caches for a specific year."""
        target_year = year if year else datetime.now().year
        
        # Get all cache keys
        all_cache_keys = list(reporting_cache._cache.keys())
        next_drafter_keys = list(next_drafter_cache._cache.keys())
        
        # Invalidate all picks list caches for the target year
        for key in all_cache_keys:
            if key.startswith(f"picks_list_{target_year}"):
                reporting_cache.delete(key)
        
        # Invalidate other related caches
        reporting_cache.delete(f"picks_counts_{target_year}")
        next_drafter_cache.delete(f"next_drafter_{target_year}")