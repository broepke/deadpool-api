import pytest
from datetime import datetime, timedelta
from ..services.reporting import ReportingService

class MockDynamoDBClient:
    """Mock DynamoDB client for testing."""
    
    async def get_players(self, year):
        return [
            {
                "id": "player1",
                "name": "Test Player 1",
                "draft_order": 1,
                "year": year
            },
            {
                "id": "player2",
                "name": "Test Player 2",
                "draft_order": 2,
                "year": year
            }
        ]
    
    async def get_player_picks(self, player_id, year):
        # Create test picks across different time periods
        base_date = datetime(year, 1, 1)
        picks = []
        
        if player_id == "player1":
            picks = [
                {
                    "person_id": "person1",
                    "year": year,
                    "timestamp": (base_date + timedelta(days=1)).isoformat()
                },
                {
                    "person_id": "person2",
                    "year": year,
                    "timestamp": (base_date + timedelta(days=32)).isoformat()  # Next month
                }
            ]
        elif player_id == "player2":
            picks = [
                {
                    "person_id": "person3",
                    "year": year,
                    "timestamp": (base_date + timedelta(days=2)).isoformat()
                },
                {
                    "person_id": "person4",
                    "year": year,
                    "timestamp": (base_date + timedelta(days=33)).isoformat()  # Next month
                }
            ]
        
        return picks
    
    async def get_person(self, person_id):
        test_data = {
            "person1": {
                "id": "person1",
                "name": "Test Person 1",
                "metadata": {
                    "Age": 65,
                    "DeathDate": "2025-01-15"  # Died in first month
                }
            },
            "person2": {
                "id": "person2",
                "name": "Test Person 2",
                "metadata": {
                    "Age": 75,
                    "DeathDate": "2025-02-20"  # Died in second month
                }
            },
            "person3": {
                "id": "person3",
                "name": "Test Person 3",
                "metadata": {
                    "Age": 55
                }
            },
            "person4": {
                "id": "person4",
                "name": "Test Person 4",
                "metadata": {
                    "Age": 85
                }
            }
        }
        return test_data.get(person_id)

@pytest.mark.asyncio
async def test_get_overview_stats():
    """Test overview statistics generation."""
    service = ReportingService(MockDynamoDBClient())
    stats = await service.get_overview_stats(2025)
    
    assert stats["total_players"] == 2
    assert stats["total_picks"] == 4
    assert stats["total_deceased"] == 2
    assert 65 <= stats["average_pick_age"] <= 75  # Should be around 70
    assert stats["pick_success_rate"] == 0.5  # 2 deceased out of 4 picks

@pytest.mark.asyncio
async def test_get_time_analytics_monthly():
    """Test monthly time analytics."""
    service = ReportingService(MockDynamoDBClient())
    analytics = await service.get_time_analytics(2025, "monthly")
    
    # Check the data structure
    assert "data" in analytics
    assert "metadata" in analytics
    
    data = analytics["data"]
    metadata = analytics["metadata"]
    
    # Should have data for two months (January and February)
    assert len(data) == 2
    
    # Check January data
    jan_data = next(d for d in data if d["period"] == "2025-01")
    assert jan_data["pick_count"] == 2  # Two picks in January
    assert jan_data["death_count"] == 1  # One death in January
    
    # Check February data
    feb_data = next(d for d in data if d["period"] == "2025-02")
    assert feb_data["pick_count"] == 2  # Two picks in February
    assert feb_data["death_count"] == 1  # One death in February
    
    # Check metadata
    assert metadata["total_periods"] == 2
    assert metadata["total_picks"] == 4
    assert metadata["total_deaths"] == 2
    assert metadata["overall_success_rate"] == 0.5
    assert metadata["period_type"] == "monthly"
    assert metadata["year"] == 2025

@pytest.mark.asyncio
async def test_get_time_analytics_daily():
    """Test daily time analytics."""
    service = ReportingService(MockDynamoDBClient())
    analytics = await service.get_time_analytics(2025, "daily")
    
    data = analytics["data"]
    
    # Should have data for four distinct days
    assert len(data) == 4
    
    # Verify each day has the correct pick count
    for day_data in data:
        assert day_data["pick_count"] == 1  # One pick per day
        assert 0 <= day_data["death_count"] <= 1  # Either 0 or 1 death per day

@pytest.mark.asyncio
async def test_get_time_analytics_weekly():
    """Test weekly time analytics."""
    service = ReportingService(MockDynamoDBClient())
    analytics = await service.get_time_analytics(2025, "weekly")
    
    data = analytics["data"]
    
    # Should have data for distinct weeks
    assert len(data) > 0
    
    # Each week should have the correct total picks
    total_picks = sum(week["pick_count"] for week in data)
    assert total_picks == 4  # Total number of test picks