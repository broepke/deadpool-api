"""Tests for the reporting service."""
from datetime import datetime, timedelta

from ..services.reporting import ReportingService


class MockDynamoDBClient:
    """Mock DynamoDB client implementing the batched interface the
    ReportingService actually uses (batch_get_player_picks / batch_get_people)."""

    PEOPLE = {
        "person1": {
            "id": "person1",
            "name": "Test Person 1",
            "metadata": {"Age": 65, "DeathDate": "2025-01-15"},  # died first month
        },
        "person2": {
            "id": "person2",
            "name": "Test Person 2",
            "metadata": {"Age": 75, "DeathDate": "2025-02-20"},  # died second month
        },
        "person3": {"id": "person3", "name": "Test Person 3", "metadata": {"Age": 55}},
        "person4": {"id": "person4", "name": "Test Person 4", "metadata": {"Age": 85}},
    }

    async def get_players(self, year):
        return [
            {"id": "player1", "name": "Test Player 1", "draft_order": 1, "year": year},
            {"id": "player2", "name": "Test Player 2", "draft_order": 2, "year": year},
        ]

    async def get_player(self, player_id, year=None):
        players = await self.get_players(year or datetime.now().year)
        return next((p for p in players if p["id"] == player_id), None)

    async def get_player_picks(self, player_id, year):
        base_date = datetime(year, 1, 1)
        if player_id == "player1":
            return [
                {"person_id": "person1", "year": year,
                 "timestamp": (base_date + timedelta(days=1)).isoformat()},
                {"person_id": "person2", "year": year,
                 "timestamp": (base_date + timedelta(days=32)).isoformat()},
            ]
        if player_id == "player2":
            return [
                {"person_id": "person3", "year": year,
                 "timestamp": (base_date + timedelta(days=2)).isoformat()},
                {"person_id": "person4", "year": year,
                 "timestamp": (base_date + timedelta(days=33)).isoformat()},
            ]
        return []

    async def batch_get_player_picks(self, player_ids, year=None):
        target_year = year or datetime.now().year
        return {pid: await self.get_player_picks(pid, target_year) for pid in player_ids}

    async def batch_get_people(self, person_ids):
        return {pid: self.PEOPLE[pid] for pid in person_ids if pid in self.PEOPLE}

    async def get_person(self, person_id):
        return self.PEOPLE.get(person_id)


async def test_get_overview_stats():
    """Overview statistics aggregate picks across all players."""
    service = ReportingService(MockDynamoDBClient())
    stats = await service.get_overview_stats(2025)

    assert stats["total_players"] == 2
    assert stats["total_picks"] == 4
    assert stats["total_deceased"] == 2
    assert 65 <= stats["average_pick_age"] <= 75  # ~70
    assert stats["pick_success_rate"] == 0.5  # 2 deceased out of 4 picks


async def test_get_time_analytics_monthly():
    """Monthly analytics bucket picks and deaths by month."""
    service = ReportingService(MockDynamoDBClient())
    analytics = await service.get_time_analytics(2025, "monthly")

    data = analytics["data"]
    metadata = analytics["metadata"]

    assert len(data) == 2  # January and February

    jan_data = next(d for d in data if d["period"] == "2025-01")
    assert jan_data["pick_count"] == 2
    assert jan_data["death_count"] == 1

    feb_data = next(d for d in data if d["period"] == "2025-02")
    assert feb_data["pick_count"] == 2
    assert feb_data["death_count"] == 1

    assert metadata["total_periods"] == 2
    assert metadata["total_picks"] == 4
    assert metadata["total_deaths"] == 2
    assert metadata["overall_success_rate"] == 0.5
    assert metadata["period_type"] == "monthly"
    assert metadata["year"] == 2025


async def test_get_time_analytics_daily():
    """Daily analytics bucket by day. Picks fall on 4 distinct days; each death
    also gets its own day bucket, so totals (not bucket count) are the invariant."""
    service = ReportingService(MockDynamoDBClient())
    analytics = await service.get_time_analytics(2025, "daily")

    data = analytics["data"]
    # 4 distinct pick days + 2 death days (Jan 15, Feb 20) = 6 buckets.
    assert len(data) == 6
    assert sum(d["pick_count"] for d in data) == 4
    assert sum(d["death_count"] for d in data) == 2
    # Periods are distinct days.
    assert len({d["period"] for d in data}) == len(data)


async def test_get_time_analytics_weekly():
    """Weekly analytics preserve the total pick count across weeks."""
    service = ReportingService(MockDynamoDBClient())
    analytics = await service.get_time_analytics(2025, "weekly")

    data = analytics["data"]
    assert len(data) > 0
    assert sum(week["pick_count"] for week in data) == 4


async def test_get_category_analysis_returns_empty_when_untracked():
    """People carry no category metadata, so category analysis returns a
    well-formed empty result rather than raising."""
    service = ReportingService(MockDynamoDBClient())
    result = await service.get_category_analysis(2026)

    assert result["data"] == []
    assert result["metadata"]["categories_tracked"] is False
    assert result["metadata"]["year"] == 2026
