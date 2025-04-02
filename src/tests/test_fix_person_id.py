"""
Test script to verify the fix for the person ID issue.
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

async def test_player_picks():
    """Test retrieving player picks to verify the fix."""
    print("\n=== Testing Player Picks Endpoint ===")
    
    # Player ID from the example
    player_id = "a4888418-70a1-709e-374a-ae0e1c797660"
    
    # Make request to the player picks endpoint
    response = client.get(f"/api/v1/deadpool/picks/{player_id}")
    
    # Print response status and data
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data.get('message')}")
        print(f"Total Items: {data.get('total')}")
        
        # Check if we have any picks
        picks = data.get("data", [])
        if picks:
            # Look for Alan Greenspan's pick
            for pick in picks:
                if pick.get("pick_person_id") == "4c78054c-5c5c-4418-a693-4bcfc90829c3":
                    print("\nFound Alan Greenspan's pick:")
                    print(f"  Person ID: {pick.get('pick_person_id')}")
                    print(f"  Person Name: {pick.get('pick_person_name')}")
                    print(f"  Person Age: {pick.get('pick_person_age')}")
                    print(f"  Birth Date: {pick.get('pick_person_birth_date')}")
                    print(f"  Death Date: {pick.get('pick_person_death_date')}")
                    print(f"  Timestamp: {pick.get('pick_timestamp')}")
                    print(f"  Year: {pick.get('year')}")
                    
                    # Verify the fix worked
                    if pick.get("pick_person_name") is not None:
                        print("\n✅ FIX VERIFIED: Person data is correctly retrieved")
                    else:
                        print("\n❌ FIX FAILED: Person data is still null")
                    
                    return
            
            print("\nCouldn't find Alan Greenspan's pick in the response")
        else:
            print("No picks found in the response")
    else:
        print(f"Error: {response.text}")

async def test_picks_by_person():
    """Test retrieving picks by person to verify the fix."""
    print("\n=== Testing Picks By Person Endpoint ===")
    
    # Person ID from the example
    person_id = "4c78054c-5c5c-4418-a693-4bcfc90829c3"
    
    # Make request to the picks by person endpoint
    response = client.get(f"/api/v1/deadpool/picks/by-person/{person_id}")
    
    # Print response status and data
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data.get('message')}")
        print(f"Total Items: {data.get('total')}")
        
        # Check if we have any picks
        picks = data.get("data", [])
        if picks:
            # Print the first pick
            pick = picks[0]
            print("\nFirst pick details:")
            print(f"  Player ID: {pick.get('player_id')}")
            print(f"  Player Name: {pick.get('player_name')}")
            print(f"  Person ID: {pick.get('pick_person_id')}")
            print(f"  Person Name: {pick.get('pick_person_name')}")
            print(f"  Person Age: {pick.get('pick_person_age')}")
            print(f"  Birth Date: {pick.get('pick_person_birth_date')}")
            print(f"  Death Date: {pick.get('pick_person_death_date')}")
            print(f"  Timestamp: {pick.get('pick_timestamp')}")
            print(f"  Year: {pick.get('year')}")
            
            # Verify the data is consistent
            if pick.get("pick_person_name") == "Alan Greenspan":
                print("\n✅ VERIFIED: Person name is correct")
            else:
                print(f"\n❌ FAILED: Person name is incorrect: {pick.get('pick_person_name')}")
        else:
            print("No picks found in the response")
    else:
        print(f"Error: {response.text}")

async def test_direct_db_access():
    """Test direct database access to verify the fix."""
    print("\n=== Testing Direct Database Access ===")
    
    # Player ID from the example
    player_id = "a4888418-70a1-709e-374a-ae0e1c797660"
    
    # Create DB client
    db = DynamoDBClient()
    
    # Get player picks directly
    picks = await db.get_player_picks(player_id, 2025)
    
    print(f"Found {len(picks)} picks for player {player_id}")
    
    # Look for Alan Greenspan's pick
    for pick in picks:
        print(f"\nPick details:")
        print(f"  Person ID: {pick.get('person_id')}")
        print(f"  Year: {pick.get('year')}")
        print(f"  Timestamp: {pick.get('timestamp')}")
        
        # Check if this is Alan Greenspan's pick
        if "4c78054c-5c5c-4418-a693-4bcfc90829c3" in str(pick.get('person_id')):
            print("\nFound Alan Greenspan's pick in database")
            
            # Get person details
            person = await db.get_person(pick.get('person_id'))
            if person:
                print(f"  Person Name: {person.get('name')}")
                print(f"  Person Status: {person.get('status')}")
                print(f"  Person Metadata: {person.get('metadata')}")
                
                # Verify the fix worked
                if person.get("name") == "Alan Greenspan":
                    print("\n✅ FIX VERIFIED: Person data is correctly retrieved from database")
                else:
                    print(f"\n❌ FIX FAILED: Person name is incorrect: {person.get('name')}")
            else:
                print("\n❌ FIX FAILED: Person data not found in database")

async def run_tests():
    """Run all tests."""
    await test_player_picks()
    await test_picks_by_person()
    await test_direct_db_access()

if __name__ == "__main__":
    asyncio.run(run_tests())