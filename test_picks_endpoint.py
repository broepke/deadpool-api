#!/usr/bin/env python3
"""
Test script to isolate the exact error in the picks endpoint
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.services.picks import PicksService
from src.utils.dynamodb import DynamoDBClient
from src.models.deadpool import PickDetail
from datetime import datetime
import json

async def test_picks_endpoint():
    """Test the picks endpoint step by step to find the exact error"""
    print("=== Testing Picks Endpoint Step by Step ===\n")
    
    try:
        # 1. Initialize the service
        print("1. Initializing PicksService...")
        db = DynamoDBClient()
        picks_service = PicksService(db)
        print("   ✓ PicksService initialized")
        
        # 2. Test get_players directly
        print("\n2. Testing get_players(2026)...")
        players = await db.get_players(2026)
        print(f"   ✓ Retrieved {len(players)} players")
        
        # 3. Test batch_get_player_picks
        print("\n3. Testing batch_get_player_picks...")
        player_ids = [p["id"] for p in players]
        all_picks = await db.batch_get_player_picks(player_ids, 2026)
        total_picks = sum(len(picks) for picks in all_picks.values())
        print(f"   ✓ Retrieved {total_picks} total picks")
        
        # 4. Test person IDs collection
        print("\n4. Testing person IDs collection...")
        person_ids = set()
        for picks in all_picks.values():
            person_ids.update(pick["person_id"] for pick in picks)
        print(f"   ✓ Collected {len(person_ids)} unique person IDs")
        
        # 5. Test batch_get_people
        print("\n5. Testing batch_get_people...")
        people = await db.batch_get_people(list(person_ids))
        print(f"   ✓ Retrieved {len(people)} people")
        
        # 6. Test PickDetail creation
        print("\n6. Testing PickDetail creation...")
        test_player = players[0]
        test_picks = all_picks.get(test_player["id"], [])
        
        if test_picks:
            test_pick = test_picks[0]
            test_person = people.get(test_pick["person_id"])
            
            if test_person:
                print(f"   Testing with player: {test_player['name']}")
                print(f"   Testing with person: {test_person['name']}")
                print(f"   Pick timestamp: {test_pick['timestamp']}")
                
                # Try to create PickDetail
                person_metadata = test_person.get("metadata", {})
                pick_detail = PickDetail(
                    player_id=test_player["id"],
                    player_name=test_player["name"],
                    draft_order=test_player["draft_order"],
                    pick_person_id=test_pick["person_id"],
                    pick_person_name=test_person["name"],
                    pick_person_age=person_metadata.get("Age"),
                    pick_person_birth_date=person_metadata.get("BirthDate"),
                    pick_person_death_date=person_metadata.get("DeathDate"),
                    pick_timestamp=test_pick["timestamp"],
                    year=2026,
                )
                print("   ✓ PickDetail created successfully")
                
                # Test JSON serialization
                try:
                    pick_dict = pick_detail.dict()
                    json_str = json.dumps(pick_dict, default=str)
                    print("   ✓ JSON serialization successful")
                except Exception as e:
                    print(f"   ❌ JSON serialization failed: {e}")
                    return
            else:
                print("   ⚠️  No person found for test pick")
        else:
            print("   ⚠️  No picks found for test player")
        
        # 7. Test the full picks service method
        print("\n7. Testing full PicksService.get_picks()...")
        try:
            result = await picks_service.get_picks(year=2026, page=1, page_size=5)
            print(f"   ✓ PicksService.get_picks() successful")
            print(f"   ✓ Returned {len(result['data'])} picks")
            print(f"   ✓ Total items: {result['total']}")
            
            # Test if the result can be JSON serialized
            try:
                json_str = json.dumps(result, default=str)
                print("   ✓ Result JSON serialization successful")
            except Exception as e:
                print(f"   ❌ Result JSON serialization failed: {e}")
                print(f"   First item type: {type(result['data'][0]) if result['data'] else 'No data'}")
                if result['data']:
                    print(f"   First item: {result['data'][0]}")
                return
                
        except Exception as e:
            print(f"   ❌ PicksService.get_picks() failed: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n=== ALL TESTS PASSED ===")
        print("The picks endpoint should be working. The issue might be:")
        print("1. Cache corruption - try clearing cache")
        print("2. Lambda timeout - the operation might be too slow")
        print("3. Memory issues - too much data being processed")
        print("4. API Gateway timeout")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_picks_endpoint())