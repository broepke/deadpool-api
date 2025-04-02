"""
Test script to verify the fix for person ID storage.
"""
import asyncio
import sys
import os
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.main import app
from src.utils.dynamodb import DynamoDBClient

client = TestClient(app)

async def test_draft_person():
    """Test the draft_person endpoint to verify it stores person IDs correctly."""
    print("\n=== Testing Draft Person Endpoint ===")
    
    # Create a test draft request
    draft_request = {
        "player_id": "a4888418-70a1-709e-374a-ae0e1c797660",  # Derek Cornwall
        "name": "Test Person " + asyncio.current_task().get_name()  # Use task name to make it unique
    }
    
    # Make request to the draft endpoint
    response = client.post("/api/v1/deadpool/draft", json=draft_request)
    
    # Print response status and data
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data.get('message')}")
        
        # Check if we have draft data
        draft_data = data.get("data", {})
        if draft_data:
            print(f"Person ID: {draft_data.get('person_id')}")
            print(f"Name: {draft_data.get('name')}")
            print(f"Is New: {draft_data.get('is_new')}")
            print(f"Pick Timestamp: {draft_data.get('pick_timestamp')}")
            
            # Get the person ID from the response
            person_id = draft_data.get('person_id')
            
            # Verify the person ID is stored correctly in the database
            await verify_person_id_storage(draft_request["player_id"], person_id)
        else:
            print("No draft data found in the response")
    else:
        print(f"Error: {response.text}")

async def verify_person_id_storage(player_id: str, person_id: str):
    """Verify that the person ID is stored correctly in the database."""
    print("\n=== Verifying Person ID Storage ===")
    
    # Create DB client
    db = DynamoDBClient()
    
    # Get player picks directly
    picks = await db.get_player_picks(player_id)
    
    # Find the pick with the given person ID
    for pick in picks:
        if pick["person_id"] == person_id:
            print(f"Found pick with person_id: {pick['person_id']}")
            print(f"Year: {pick['year']}")
            print(f"Timestamp: {pick['timestamp']}")
            
            # Verify the person ID is a string, not a dictionary
            if isinstance(pick["person_id"], str) and not pick["person_id"].startswith("{"):
                print("\n✅ FIX VERIFIED: Person ID is stored correctly as a string")
            else:
                print(f"\n❌ FIX FAILED: Person ID is not stored correctly: {pick['person_id']}")
            
            return
    
    print(f"\n❌ FIX FAILED: No pick found with person_id: {person_id}")

async def run_tests():
    """Run all tests."""
    await test_draft_person()

if __name__ == "__main__":
    asyncio.run(run_tests())