"""
Test script to verify the fix for the reporting endpoints.
"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.main import app
from src.utils.dynamodb import DynamoDBClient
from src.services.reporting import ReportingService

client = TestClient(app)

async def test_overview_stats():
    """Test the overview stats endpoint to verify the fix."""
    print("\n=== Testing Overview Stats Endpoint ===")
    
    # Make request to the overview stats endpoint
    response = client.get("/api/v1/deadpool/reporting/overview")
    
    # Print response status and data
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data.get('message')}")
        
        # Check if we have overview stats
        stats = data.get("data", {})
        if stats:
            print(f"Total Players: {stats.get('total_players')}")
            print(f"Total Picks: {stats.get('total_picks')}")
            print(f"Total Deceased: {stats.get('total_deceased')}")
            print(f"Average Pick Age: {stats.get('average_pick_age')}")
            print(f"Most Popular Age Range: {stats.get('most_popular_age_range')}")
            print(f"Most Successful Age Range: {stats.get('most_successful_age_range')}")
            print(f"Pick Success Rate: {stats.get('pick_success_rate')}")
            
            # Verify the fix worked
            if stats.get("total_picks") > 0:
                print("\n✅ FIX VERIFIED: Overview stats are correctly calculated")
            else:
                print("\n❌ FIX FAILED: No picks found in overview stats")
        else:
            print("No overview stats found in the response")
    else:
        print(f"Error: {response.text}")

async def test_player_analytics():
    """Test the player analytics endpoint to verify the fix."""
    print("\n=== Testing Player Analytics Endpoint ===")
    
    # Player ID for Derek Cornwall
    player_id = "a4888418-70a1-709e-374a-ae0e1c797660"
    
    # Make request to the player analytics endpoint
    response = client.get(f"/api/v1/deadpool/reporting/player-analytics?player_id={player_id}")
    
    # Print response status and data
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data.get('message')}")
        
        # Check if we have player analytics
        analytics = data.get("data", [])
        if analytics:
            player_data = analytics[0]
            print(f"Player ID: {player_data.get('player_id')}")
            print(f"Player Name: {player_data.get('player_name')}")
            print(f"Preferred Age Ranges: {player_data.get('preferred_age_ranges')}")
            print(f"Pick Timing Pattern: {player_data.get('pick_timing_pattern')}")
            print(f"Success Rate: {player_data.get('success_rate')}")
            
            # Check points data
            points = player_data.get("points", {})
            print(f"Current Points: {points.get('current')}")
            print(f"Total Potential Points: {points.get('total_potential')}")
            print(f"Remaining Points: {points.get('remaining')}")
            
            # Verify the fix worked
            if points.get("total_potential") > 0:
                print("\n✅ FIX VERIFIED: Player analytics are correctly calculated")
            else:
                print("\n❌ FIX FAILED: No potential points found in player analytics")
        else:
            print("No player analytics found in the response")
    else:
        print(f"Error: {response.text}")

async def test_direct_reporting():
    """Test direct reporting service to verify the fix."""
    print("\n=== Testing Direct Reporting Service ===")
    
    # Create DB client and reporting service
    db = DynamoDBClient()
    reporting_service = ReportingService(db)
    
    # Get overview stats directly
    stats = await reporting_service.get_overview_stats(2025)
    
    print(f"Total Players: {stats.get('total_players')}")
    print(f"Total Picks: {stats.get('total_picks')}")
    print(f"Total Deceased: {stats.get('total_deceased')}")
    
    # Verify the fix worked
    if stats.get("total_picks") > 0:
        print("\n✅ FIX VERIFIED: Direct reporting service correctly calculates stats")
    else:
        print("\n❌ FIX FAILED: No picks found in direct reporting service")

async def run_tests():
    """Run all tests."""
    await test_overview_stats()
    await test_player_analytics()
    await test_direct_reporting()

if __name__ == "__main__":
    asyncio.run(run_tests())