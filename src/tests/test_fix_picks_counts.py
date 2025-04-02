"""
Test script to verify the fix for the picks-counts endpoint.
"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.main import app
from src.utils.dynamodb import DynamoDBClient
from src.services.picks import PicksService

client = TestClient(app)

async def test_picks_counts():
    """Test the picks-counts endpoint to verify the fix."""
    print("\n=== Testing Picks Counts Endpoint ===")
    
    # Make request to the picks-counts endpoint
    response = client.get("/api/v1/deadpool/picks-counts")
    
    # Print response status and data
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data.get('message')}")
        
        # Check if we have any pick counts
        pick_counts = data.get("data", [])
        if pick_counts:
            # Look for Derek Cornwall's pick count
            for pick_count in pick_counts:
                if pick_count.get("player_id") == "a4888418-70a1-709e-374a-ae0e1c797660":
                    print("\nFound Derek Cornwall's pick count:")
                    print(f"  Player ID: {pick_count.get('player_id')}")
                    print(f"  Player Name: {pick_count.get('player_name')}")
                    print(f"  Draft Order: {pick_count.get('draft_order')}")
                    print(f"  Pick Count: {pick_count.get('pick_count')}")
                    print(f"  Year: {pick_count.get('year')}")
                    return
            
            print("\nCouldn't find Derek Cornwall's pick count in the response")
        else:
            print("No pick counts found in the response")
    else:
        print(f"Error: {response.text}")

async def test_direct_picks_count():
    """Test direct calculation of pick counts to verify the fix."""
    print("\n=== Testing Direct Picks Count Calculation ===")
    
    # Player ID for Derek Cornwall
    player_id = "a4888418-70a1-709e-374a-ae0e1c797660"
    
    # Create DB client and picks service
    db = DynamoDBClient()
    picks_service = PicksService(db)
    
    # Get player picks directly
    picks = await db.get_player_picks(player_id, 2025)
    
    print(f"Found {len(picks)} picks for player {player_id}")
    
    # Get all person IDs from picks
    person_ids = [pick["person_id"] for pick in picks]
    
    # Get all people
    people = await db.batch_get_people(person_ids)
    
    # Count alive people
    alive_count = 0
    for pick in picks:
        # Extract the actual person_id if it's stored as a string representation of a dictionary
        actual_person_id = pick["person_id"]
        if isinstance(actual_person_id, str) and actual_person_id.startswith("{") and "person_id" in actual_person_id:
            try:
                import ast
                person_dict = ast.literal_eval(actual_person_id)
                actual_person_id = person_dict.get("person_id")
                print(f"Extracted person_id from dictionary string: {actual_person_id}")
            except Exception as e:
                print(f"Error parsing person_id from string: {e}")
        
        # Get person using the extracted ID
        person = people.get(actual_person_id)
        if person:
            print(f"Person: {person.get('name')}, Status: {'alive' if 'DeathDate' not in person.get('metadata', {}) else 'deceased'}")
            if "DeathDate" not in person.get("metadata", {}):
                alive_count += 1
    
    print(f"\nTotal alive picks: {alive_count}")
    
    # Get pick counts from the service
    result = await picks_service.get_picks_counts(2025)
    
    # Find Derek Cornwall's pick count
    for pick_count in result.get("data", []):
        if pick_count.player_id == player_id:
            print(f"\nPick count from service: {pick_count.pick_count}")
            
            # Verify the counts match
            if pick_count.pick_count == alive_count:
                print("\n✅ FIX VERIFIED: Pick counts match")
            else:
                print(f"\n❌ FIX FAILED: Pick counts don't match (service: {pick_count.pick_count}, direct: {alive_count})")
            
            break

async def run_tests():
    """Run all tests."""
    await test_picks_counts()
    await test_direct_picks_count()

if __name__ == "__main__":
    asyncio.run(run_tests())