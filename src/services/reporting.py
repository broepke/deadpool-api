from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from collections import defaultdict
from ..utils.dynamodb import DynamoDBClient

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
            {"range": "80+", "min": 80, "max": float('inf')}
        ]

    async def get_overview_stats(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get high-level statistics about the current state of the game.
        
        Args:
            year: Optional year to filter statistics (defaults to current year)
            
        Returns:
            Dictionary containing overview statistics
        """
        try:
            target_year = year if year else datetime.now().year
            
            # Get all players for the year
            players = await self.db.get_players(target_year)
            
            # Initialize age range statistics
            age_ranges = {
                "0-29": {"count": 0, "deceased": 0},
                "30-39": {"count": 0, "deceased": 0},
                "40-49": {"count": 0, "deceased": 0},
                "50-59": {"count": 0, "deceased": 0},
                "60-69": {"count": 0, "deceased": 0},
                "70-79": {"count": 0, "deceased": 0},
                "80+": {"count": 0, "deceased": 0},
            }
            
            total_picks = 0
            total_deceased = 0
            total_age = 0
            
            # Analyze all picks
            for player in players:
                picks = await self.db.get_player_picks(player["id"], target_year)
                for pick in picks:
                    person = await self.db.get_person(pick["person_id"])
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
            
            # Calculate most popular and most successful age ranges
            most_popular_range = max(age_ranges.items(), key=lambda x: x[1]["count"])[0]
            
            # Calculate success rates for each range
            success_rates = {}
            for range_name, stats in age_ranges.items():
                if stats["count"] > 0:
                    success_rates[range_name] = stats["deceased"] / stats["count"]
                else:
                    success_rates[range_name] = 0
            
            most_successful_range = max(success_rates.items(), key=lambda x: x[1])[0]
            
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

    async def get_time_analytics(
        self,
        year: Optional[int] = None,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Get time-based analytics about picks and deaths.
        
        Args:
            year: Optional year to filter statistics (defaults to current year)
            period: Analysis period ('daily', 'weekly', 'monthly')
            
        Returns:
            Dictionary containing time-based analytics
        """
        try:
            target_year = year if year else datetime.now().year
            
            # Initialize data structures for time-based analysis
            time_data = defaultdict(lambda: {
                "pick_count": 0,
                "death_count": 0,
                "total_age": 0,
                "picks": []  # Store picks for calculating averages
            })
            
            # First, collect all deaths in the target year
            all_people = await self.db.get_people()
            for person in all_people:
                death_date = person.get("metadata", {}).get("DeathDate")
                if death_date:
                    death_time = datetime.strptime(death_date, "%Y-%m-%d")
                    if death_time.year == target_year:
                        death_period_key = self._get_period_key(death_time, period)
                        # Initialize period data if it doesn't exist
                        if death_period_key not in time_data:
                            time_data[death_period_key] = {
                                "pick_count": 0,
                                "death_count": 0,
                                "total_age": 0,
                                "picks": []
                            }
                        time_data[death_period_key]["death_count"] += 1
            
            # Get all players for the year
            players = await self.db.get_players(target_year)
            
            # Then collect all picks and analyze their timing
            for player in players:
                picks = await self.db.get_player_picks(player["id"], target_year)
                for pick in picks:
                    if not pick.get("timestamp"):
                        continue
                        
                    pick_time = datetime.fromisoformat(pick["timestamp"])
                    period_key = self._get_period_key(pick_time, period)
                    
                    person = await self.db.get_person(pick["person_id"])
                    if person:
                        metadata = person.get("metadata", {})
                        age = metadata.get("Age", 0)
                        
                        # Initialize period data if it doesn't exist
                        if period_key not in time_data:
                            time_data[period_key] = {
                                "pick_count": 0,
                                "death_count": 0,
                                "total_age": 0,
                                "picks": []
                            }
                        
                        # Add pick data
                        time_data[period_key]["pick_count"] += 1
                        time_data[period_key]["total_age"] += age
                        time_data[period_key]["picks"].append({
                            "age": age
                        })
            
            # Convert defaultdict to list of analytics entries
            analytics_data = []
            total_deaths = 0
            
            for period_key, data in sorted(time_data.items()):
                picks_count = data["pick_count"]
                death_count = data["death_count"]
                total_deaths += death_count
                
                analytics_data.append({
                    "period": period_key,
                    "pick_count": picks_count,
                    "death_count": death_count,
                    "success_rate": death_count / picks_count if picks_count > 0 else 0,
                    "average_age": data["total_age"] / picks_count if picks_count > 0 else 0,
                    "timestamp": datetime.strptime(period_key, "%Y-%m" if period == "monthly" else "%Y-%m-%d")
                })
            
            # Calculate metadata
            total_picks = sum(data["pick_count"] for data in analytics_data)
            
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

    async def get_demographic_analysis(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get detailed demographic analysis of picks.
        
        Args:
            year: Optional year to filter statistics (defaults to current year)
            
        Returns:
            Dictionary containing demographic analysis
        """
        try:
            target_year = year if year else datetime.now().year
            
            # Initialize age group data
            age_groups = []
            for range_info in self.age_ranges:
                age_groups.append({
                    "range": range_info["range"],
                    "pick_count": 0,
                    "death_count": 0,
                    "total_score": 0,
                    "picks": []  # Store picks for calculating averages
                })
            
            # Get all players for the year
            players = await self.db.get_players(target_year)
            
            # Analyze all picks
            total_picks = 0
            total_deaths = 0
            
            for player in players:
                picks = await self.db.get_player_picks(player["id"], target_year)
                for pick in picks:
                    person = await self.db.get_person(pick["person_id"])
                    if person:
                        total_picks += 1
                        age = person.get("metadata", {}).get("Age", 0)
                        
                        # Find appropriate age group
                        for group in age_groups:
                            range_info = next(r for r in self.age_ranges if r["range"] == group["range"])
                            if range_info["min"] <= age <= range_info["max"]:
                                group["pick_count"] += 1
                                group["picks"].append({
                                    "age": age,
                                    "person_id": person["id"],
                                    "person_name": person["name"]
                                })
                                
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
                group["success_rate"] = group["death_count"] / group["pick_count"] if group["pick_count"] > 0 else 0
                group["average_score"] = group["total_score"] / group["death_count"] if group["death_count"] > 0 else 0
                del group["picks"]  # Remove detailed pick data from response
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

    async def get_player_analytics(
        self,
        player_id: Optional[str] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get detailed analytics for player(s).
        
        Args:
            player_id: Optional player ID to filter analytics
            year: Optional year to filter statistics (defaults to current year)
            
        Returns:
            Dictionary containing player analytics
        """
        try:
            target_year = year if year else datetime.now().year
            
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
                    "metadata": {
                        "year": target_year,
                        "total_players": 0,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            
            player_analytics = []
            total_picks = 0
            total_deaths = 0
            
            for player in players:
                # Get all picks for this player
                picks = await self.db.get_player_picks(player["id"], target_year)
                
                # Initialize player statistics
                age_preferences = defaultdict(int)
                pick_timing = {
                    "morning": 0,    # 6-12
                    "afternoon": 0,  # 12-18
                    "evening": 0,    # 18-24
                    "night": 0       # 0-6
                }
                score_progression = []
                current_score = 0
                deceased_picks = 0
                
                # Analyze each pick
                for pick in picks:
                    total_picks += 1
                    
                    # Get person details
                    person = await self.db.get_person(pick["person_id"])
                    if person:
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
                                # Calculate score: 50 + (100 - age)
                                score = 50 + (100 - age)
                                current_score += score
                                
                        # Add current score to progression
                        score_progression.append(current_score)
                
                # Calculate preferred age ranges (sorted by count)
                preferred_ranges = sorted(
                    [(range_name, count) for range_name, count in age_preferences.items()],
                    key=lambda x: x[1],
                    reverse=True
                )
                preferred_age_ranges = [range_name for range_name, _ in preferred_ranges]
                
                # Determine pick timing pattern
                timing_pattern = "random"
                if pick_timing["night"] > 0.8 * len(picks):
                    timing_pattern = "night owl"
                elif pick_timing["morning"] > 0.8 * len(picks):
                    timing_pattern = "early bird"
                elif pick_timing["afternoon"] > 0.8 * len(picks):
                    timing_pattern = "afternoon regular"
                elif pick_timing["evening"] > 0.8 * len(picks):
                    timing_pattern = "evening regular"
                
                player_stats = {
                    "player_id": player["id"],
                    "player_name": player["name"],
                    "preferred_age_ranges": preferred_age_ranges,
                    "preferred_categories": [],  # Categories not implemented
                    "pick_timing_pattern": timing_pattern,
                    "success_rate": deceased_picks / len(picks) if picks else 0,
                    "score_progression": score_progression
                }
                
                player_analytics.append(player_stats)
            
            # Sort by final score (last value in score_progression)
            player_analytics.sort(
                key=lambda x: x["score_progression"][-1] if x["score_progression"] else 0,
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