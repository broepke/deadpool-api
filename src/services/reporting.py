"""Service class for handling reporting and analytics functionality."""
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from collections import defaultdict
from ..utils.dynamodb import DynamoDBClient
from ..utils.caching import reporting_cache

class ReportingService:
    """Service class for handling reporting and analytics functionality."""
    
    def __init__(self, db_client: DynamoDBClient):
        self.db = db_client
        self.age_ranges = [
            {"range": "0-29", "min": 0, "max": 29},
            {"range": "30-39", "min": 30, "max": 39},
            {"range": "40-49", "min": 40, "max": 49},
            {"range": "50-59", "min": 50, "max": 59},
            {"range": "60-69", "min": 60, "max": 69},
            {"range": "70-79", "min": 70, "max": 79},
            {"range": "80-89", "min": 80, "max": 89},
            {"range": "90-99", "min": 90, "max": 99},
            {"range": "100+", "min": 100, "max": float('inf')}
        ]

    async def get_overview_stats(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Get high-level statistics about the current state of the game."""
        target_year = year if year else datetime.now().year
        cache_key = f"overview_stats_{target_year}"

        return await reporting_cache.get_or_compute(
            cache_key,
            lambda: self._compute_overview_stats(target_year)
        )

    async def _compute_overview_stats(self, target_year: int) -> Dict[str, Any]:
        """Compute overview statistics with optimized batch operations."""
        try:
            # Get all players for the year
            players = await self.db.get_players(target_year)
            if not players:
                return self._empty_overview_stats(target_year)

            # Batch get all picks for all players
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all person IDs from picks
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            # Initialize age range statistics
            age_ranges = {
                range_info["range"]: {"count": 0, "deceased": 0}
                for range_info in self.age_ranges
            }

            total_picks = 0
            total_deceased = 0
            total_age = 0

            # Process all picks with optimized data access
            for player_picks in all_picks.values():
                for pick in player_picks:
                    # Get person using the person ID
                    person = people.get(pick["person_id"])
                    if person:
                        total_picks += 1
                        age = person.get("metadata", {}).get("Age", 0)
                        total_age += age

                        # Categorize into age ranges
                        age_range = self._get_age_range(age)
                        if age_range:
                            age_ranges[age_range]["count"] += 1

                            # Check if deceased in target year
                            death_date = person.get("metadata", {}).get("DeathDate")
                            if death_date:
                                death_year = datetime.strptime(death_date, "%Y-%m-%d").year
                                if death_year == target_year:
                                    total_deceased += 1
                                    age_ranges[age_range]["deceased"] += 1

            # Calculate most popular and successful ranges
            most_popular_range = max(
                age_ranges.items(),
                key=lambda x: x[1]["count"]
            )[0]

            success_rates = {
                range_name: stats["deceased"] / stats["count"]
                if stats["count"] > 0 else 0
                for range_name, stats in age_ranges.items()
            }

            most_successful_range = max(
                success_rates.items(),
                key=lambda x: x[1]
            )[0]

            return {
                "total_players": len(players),
                "total_picks": total_picks,
                "total_deceased": total_deceased,
                "average_pick_age": total_age / total_picks if total_picks > 0 else 0,
                "most_popular_age_range": most_popular_range,
                "most_successful_age_range": most_successful_range,
                "pick_success_rate": total_deceased / total_picks if total_picks > 0 else 0,
                "age_distribution": age_ranges,
                "updated_at": datetime.utcnow().isoformat(),
                "year": target_year
            }

        except Exception as e:
            raise Exception(f"Error generating overview stats: {str(e)}")

    def _empty_overview_stats(self, year: int) -> Dict[str, Any]:
        """Return empty overview statistics structure."""
        return {
            "total_players": 0,
            "total_picks": 0,
            "total_deceased": 0,
            "average_pick_age": 0,
            "most_popular_age_range": None,
            "most_successful_age_range": None,
            "pick_success_rate": 0,
            "age_distribution": {
                range_info["range"]: {"count": 0, "deceased": 0}
                for range_info in self.age_ranges
            },
            "updated_at": datetime.utcnow().isoformat(),
            "year": year
        }

    async def get_time_analytics(
        self,
        year: Optional[int] = None,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """Get time-based analytics about picks and deaths."""
        target_year = year if year else datetime.now().year
        cache_key = f"time_analytics_{target_year}_{period}"

        return await reporting_cache.get_or_compute(
            cache_key,
            lambda: self._compute_time_analytics(target_year, period)
        )

    async def _compute_time_analytics(
        self,
        target_year: int,
        period: str
    ) -> Dict[str, Any]:
        """Compute time-based analytics with optimized batch operations."""
        try:
            # Get all players
            players = await self.db.get_players(target_year)
            if not players:
                return {"data": [], "metadata": self._empty_time_metadata(target_year, period)}

            # Batch get all picks
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all person IDs
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            # Initialize time-based analysis
            time_data = defaultdict(lambda: {
                "pick_count": 0,
                "death_count": 0,
                "total_age": 0,
                "picks": []
            })

            # Process all picks and deaths
            for picks in all_picks.values():
                for pick in picks:
                    # Get person using the person ID
                    person = people.get(pick["person_id"])
                    if not person:
                        continue

                    pick_time = datetime.fromisoformat(pick["timestamp"])
                    period_key = self._get_period_key(pick_time, period)
                    age = person.get("metadata", {}).get("Age", 0)

                    time_data[period_key]["pick_count"] += 1
                    time_data[period_key]["total_age"] += age
                    time_data[period_key]["picks"].append({"age": age})

                    # Check for death in target year
                    death_date = person.get("metadata", {}).get("DeathDate")
                    if death_date:
                        death_time = datetime.strptime(death_date, "%Y-%m-%d")
                        if death_time.year == target_year:
                            death_period_key = self._get_period_key(death_time, period)
                            time_data[death_period_key]["death_count"] += 1

            # Convert to analytics entries
            analytics_data = []
            total_picks = 0
            total_deaths = 0

            for period_key, data in sorted(time_data.items()):
                picks_count = data["pick_count"]
                death_count = data["death_count"]
                total_picks += picks_count
                total_deaths += death_count

                analytics_data.append({
                    "period": period_key,
                    "pick_count": picks_count,
                    "death_count": death_count,
                    "success_rate": death_count / picks_count if picks_count > 0 else 0,
                    "average_age": data["total_age"] / picks_count if picks_count > 0 else 0,
                    "timestamp": datetime.strptime(
                        period_key,
                        "%Y-%m" if period == "monthly" else "%Y-%m-%d"
                    )
                })

            metadata = {
                "total_periods": len(analytics_data),
                "total_picks": total_picks,
                "total_deaths": total_deaths,
                "overall_success_rate": total_deaths / total_picks if total_picks > 0 else 0,
                "average_picks_per_period": total_picks / len(analytics_data) if analytics_data else 0,
                "period_type": period,
                "year": target_year
            }

            return {
                "data": analytics_data,
                "metadata": metadata
            }

        except Exception as e:
            raise Exception(f"Error generating time analytics: {str(e)}")

    def _empty_time_metadata(self, year: int, period: str) -> Dict[str, Any]:
        """Return empty time analytics metadata structure."""
        return {
            "total_periods": 0,
            "total_picks": 0,
            "total_deaths": 0,
            "overall_success_rate": 0,
            "average_picks_per_period": 0,
            "period_type": period,
            "year": year
        }

    async def get_demographic_analysis(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get demographic analysis of picks."""
        target_year = year if year else datetime.now().year
        cache_key = f"demographic_analysis_{target_year}"

        return await reporting_cache.get_or_compute(
            cache_key,
            lambda: self._compute_demographic_analysis(target_year)
        )

    async def _compute_demographic_analysis(self, target_year: int) -> Dict[str, Any]:
        """Compute demographic analysis with optimized batch operations."""
        try:
            # Get all players
            players = await self.db.get_players(target_year)
            if not players:
                return {"data": [], "metadata": self._empty_demographic_metadata(target_year)}

            # Batch get all picks
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all person IDs
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            # Initialize age group data
            age_groups = []
            for range_info in self.age_ranges:
                age_groups.append({
                    "range": range_info["range"],
                    "pick_count": 0,
                    "death_count": 0,
                    "total_score": 0
                })

            total_picks = 0
            total_deaths = 0

            # Process all picks
            for picks in all_picks.values():
                for pick in picks:
                    # Get person using the person ID
                    person = people.get(pick["person_id"])
                    if not person:
                        continue

                    total_picks += 1
                    age = person.get("metadata", {}).get("Age", 0)

                    # Find appropriate age group
                    for group in age_groups:
                        range_info = next(
                            r for r in self.age_ranges
                            if r["range"] == group["range"]
                        )
                        if range_info["min"] <= age <= range_info["max"]:
                            group["pick_count"] += 1

                            # Check if deceased in target year
                            death_date = person.get("metadata", {}).get("DeathDate")
                            if death_date:
                                death_year = datetime.strptime(death_date, "%Y-%m-%d").year
                                if death_year == target_year:
                                    total_deaths += 1
                                    group["death_count"] += 1
                                    # Calculate score: 50 + (100 - age)
                                    score = 50 + (100 - age)
                                    group["total_score"] += score
                            break

            # Calculate success rates and average scores
            for group in age_groups:
                group["success_rate"] = (
                    group["death_count"] / group["pick_count"]
                    if group["pick_count"] > 0 else 0
                )
                group["average_score"] = (
                    group["total_score"] / group["death_count"]
                    if group["death_count"] > 0 else 0
                )
                del group["total_score"]  # Remove intermediate calculation

            # Find most popular and successful ranges
            most_popular = max(age_groups, key=lambda x: x["pick_count"])
            most_successful = max(age_groups, key=lambda x: x["success_rate"])

            metadata = {
                "total_picks": total_picks,
                "total_deaths": total_deaths,
                "overall_success_rate": total_deaths / total_picks if total_picks > 0 else 0,
                "most_popular_range": most_popular["range"],
                "most_successful_range": most_successful["range"],
                "year": target_year,
                "updated_at": datetime.utcnow().isoformat()
            }

            return {
                "data": age_groups,
                "metadata": metadata
            }

        except Exception as e:
            raise Exception(f"Error generating demographic analysis: {str(e)}")

    def _empty_demographic_metadata(self, year: int) -> Dict[str, Any]:
        """Return empty demographic analysis metadata structure."""
        return {
            "total_picks": 0,
            "total_deaths": 0,
            "overall_success_rate": 0,
            "most_popular_range": None,
            "most_successful_range": None,
            "year": year,
            "updated_at": datetime.utcnow().isoformat()
        }

    async def get_player_analytics(
        self,
        player_id: Optional[str] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get detailed analytics for player(s)."""
        target_year = year if year else datetime.now().year
        cache_key = f"player_analytics_{player_id or 'all'}_{target_year}"

        return await reporting_cache.get_or_compute(
            cache_key,
            lambda: self._compute_player_analytics(player_id, target_year)
        )

    async def _compute_player_analytics(
        self,
        player_id: Optional[str],
        target_year: int
    ) -> Dict[str, Any]:
        """Compute player analytics with optimized batch operations."""
        try:
            # Get players to analyze
            players = []
            if player_id:
                player = await self.db.get_player(player_id, target_year)
                if player:
                    players = [player]
            else:
                players = await self.db.get_players(target_year)

            if not players:
                return {
                    "data": [],
                    "metadata": self._empty_player_analytics_metadata(target_year)
                }

            # Batch get all picks
            player_ids = [p["id"] for p in players]
            all_picks = await self.db.batch_get_player_picks(player_ids, target_year)

            # Collect all person IDs
            person_ids = set()
            for picks in all_picks.values():
                person_ids.update(pick["person_id"] for pick in picks)

            # Batch get all people
            people = await self.db.batch_get_people(list(person_ids))

            player_analytics = []
            total_picks = 0
            total_deaths = 0

            for player in players:
                picks = all_picks.get(player["id"], [])
                if not picks:
                    continue

                # Initialize player statistics
                age_preferences = defaultdict(int)
                pick_timing = {
                    "morning": 0,    # 6-12
                    "afternoon": 0,  # 12-18
                    "evening": 0,    # 18-24
                    "night": 0       # 0-6
                }
                score_progression = []
                deceased_picks = 0
                # Track death dates and scores for progression
                death_events = []

                # Analyze each pick
                for pick in picks:
                    total_picks += 1
                    # Get person using the person ID
                    person = people.get(pick["person_id"])
                    if not person:
                        continue

                    # Age analysis
                    age = person.get("metadata", {}).get("Age", 0)
                    age_range = self._get_age_range(age)
                    if age_range:
                        age_preferences[age_range] += 1

                    # Pick timing analysis
                    if pick.get("timestamp"):
                        pick_time = datetime.fromisoformat(pick["timestamp"])
                        hour = pick_time.hour
                        if 6 <= hour < 12:
                            pick_timing["morning"] += 1
                        elif 12 <= hour < 18:
                            pick_timing["afternoon"] += 1
                        elif 18 <= hour < 24:
                            pick_timing["evening"] += 1
                        else:
                            pick_timing["night"] += 1

                    # Death analysis
                    death_date = person.get("metadata", {}).get("DeathDate")
                    if death_date:
                        death_year = datetime.strptime(death_date, "%Y-%m-%d").year
                        if death_year == target_year:
                            deceased_picks += 1
                            total_deaths += 1
                            # Track death date and person info
                            death_events.append({
                                "date": death_date,
                                "person_name": person.get("name", "Unknown"),
                                "age": age
                            })

                # Calculate preferred age ranges
                preferred_ranges = sorted(
                    [(range_name, count) for range_name, count in age_preferences.items()],
                    key=lambda x: x[1],
                    reverse=True
                )
                preferred_age_ranges = [range_name for range_name, _ in preferred_ranges]

                # Determine pick timing pattern
                timing_pattern = "random"
                total_picks_count = len(picks)
                if pick_timing["night"] > 0.8 * total_picks_count:
                    timing_pattern = "night owl"
                elif pick_timing["morning"] > 0.8 * total_picks_count:
                    timing_pattern = "early bird"
                elif pick_timing["afternoon"] > 0.8 * total_picks_count:
                    timing_pattern = "afternoon regular"
                elif pick_timing["evening"] > 0.8 * total_picks_count:
                    timing_pattern = "evening regular"

                # Build score progression with dates
                # Sort death events by date
                death_events.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
                
                # Initialize score progression with dates
                score_progression = []
                running_total = 0
                
                # Add initial zero score entry if there are death events
                if death_events:
                    score_progression.append({"score": 0, "date": None})
                
                # Add each death event with its date and cumulative score
                for event in death_events:
                    # Calculate individual score for this death: 50 + (100 - age)
                    individual_score = 50 + (100 - event["age"])
                    
                    # Add to running total
                    running_total += individual_score
                    
                    score_progression.append({
                        "score": running_total,
                        "date": event["date"],
                        "person_name": event["person_name"]
                    })
                
                # If no deaths, add a single zero entry
                if not score_progression:
                    score_progression.append({"score": 0, "date": None})
                
                # Calculate points for the new points category
                current_points = running_total  # Current points is the sum of points from deceased picks
                
                # Calculate total potential points and remaining points
                total_potential_points = 0
                remaining_points = 0
                
                # Process all picks to calculate potential and remaining points
                for pick in picks:
                    # Get person using the person ID
                    person = people.get(pick["person_id"])
                    if not person:
                        continue
                        
                    age = person.get("metadata", {}).get("Age", 0)
                    potential_score = 50 + (100 - age)
                    total_potential_points += potential_score
                    
                    # Check if the person is still alive (no death date or death date in future years)
                    death_date = person.get("metadata", {}).get("DeathDate")
                    is_alive = True
                    if death_date:
                        death_year = datetime.strptime(death_date, "%Y-%m-%d").year
                        if death_year <= target_year:
                            is_alive = False
                    
                    # Add to remaining points if the person is still alive
                    if is_alive:
                        remaining_points += potential_score
                
                player_stats = {
                    "player_id": player["id"],
                    "player_name": player["name"],
                    "preferred_age_ranges": preferred_age_ranges,
                    "pick_timing_pattern": timing_pattern,
                    "success_rate": deceased_picks / len(picks) if picks else 0,
                    "score_progression": score_progression,
                    "points": {
                        "current": current_points,
                        "total_potential": total_potential_points,
                        "remaining": remaining_points
                    }
                }

                player_analytics.append(player_stats)

            # Sort by final score
            player_analytics.sort(
                key=lambda x: x["score_progression"][-1]["score"] if x["score_progression"] else 0,
                reverse=True
            )

            metadata = {
                "year": target_year,
                "total_players": len(players),
                "total_picks": total_picks,
                "total_deaths": total_deaths,
                "overall_success_rate": total_deaths / total_picks if total_picks > 0 else 0,
                "updated_at": datetime.utcnow().isoformat()
            }

            return {
                "data": player_analytics,
                "metadata": metadata
            }

        except Exception as e:
            raise Exception(f"Error generating player analytics: {str(e)}")

    def _empty_player_analytics_metadata(self, year: int) -> Dict[str, Any]:
        """Return empty player analytics metadata structure."""
        return {
            "year": year,
            "total_players": 0,
            "total_picks": 0,
            "total_deaths": 0,
            "overall_success_rate": 0,
            "updated_at": datetime.utcnow().isoformat()
        }

    def _get_age_range(self, age: int) -> Optional[str]:
        """Helper method to categorize age into ranges."""
        for range_info in self.age_ranges:
            if range_info["min"] <= age <= range_info["max"]:
                return range_info["range"]
        return None

    def _get_period_key(self, date: datetime, period: str) -> str:
        """Helper method to generate period key based on period type."""
        if period == "monthly":
            return date.strftime("%Y-%m")
        elif period == "weekly":
            # Get the Monday of the week
            monday = date - timedelta(days=date.weekday())
            return monday.strftime("%Y-%m-%d")
        else:  # daily
            return date.strftime("%Y-%m-%d")