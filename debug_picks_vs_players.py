#!/usr/bin/env python3
"""
Debug script to compare why players endpoint works but picks endpoint fails
"""
import boto3
import json
from datetime import datetime

def debug_picks_vs_players():
    """Compare the data flow between working players endpoint and failing picks endpoint"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Deadpool')
    
    print("=== Players vs Picks Endpoint Debug ===\n")
    
    # 1. Test the same data flow as players endpoint
    print("1. Testing players endpoint data flow...")
    try:
        # This is exactly what get_players(2026) does
        response = table.query(
            KeyConditionExpression="PK = :year_key",
            ExpressionAttributeValues={":year_key": "YEAR#2026"}
        )
        draft_orders = response.get("Items", [])
        print(f"   ✓ Draft orders query successful: {len(draft_orders)} records")
        
        # Extract player IDs like the players endpoint does
        player_info = []
        for order in draft_orders:
            parts = order["SK"].split("#")
            if len(parts) >= 4:
                draft_order = int(parts[1])
                player_id = parts[3]
                player_info.append((player_id, draft_order))
        
        print(f"   ✓ Player info extracted: {len(player_info)} players")
        
        # Test batch get like players endpoint does
        player_keys = [
            {"PK": f"PLAYER#{player_id}", "SK": "DETAILS"}
            for player_id, _ in player_info
        ]
        
        response = dynamodb.batch_get_item(
            RequestItems={
                'Deadpool': {
                    'Keys': player_keys,
                    'ConsistentRead': True
                }
            }
        )
        
        players = response['Responses']['Deadpool']
        print(f"   ✓ Batch get players successful: {len(players)} players retrieved")
        
    except Exception as e:
        print(f"   ❌ Players endpoint flow failed: {e}")
        return
    
    # 2. Test picks service data flow
    print("\n2. Testing picks service data flow...")
    try:
        # This is what PicksService._compute_picks_list does
        # First it calls get_players(2026) - which we know works
        print("   ✓ get_players(2026) would succeed (tested above)")
        
        # Then it calls batch_get_player_picks for all players
        player_ids = [player_id for player_id, _ in player_info]
        print(f"   Testing batch_get_player_picks for {len(player_ids)} players...")
        
        all_picks = {}
        for player_id in player_ids:
            # This is what batch_get_player_picks does for each player
            params = {
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "ExpressionAttributeValues": {
                    ":pk": f"PLAYER#{player_id}",
                    ":sk_prefix": "PICK#2026#"
                }
            }
            
            response = table.query(**params)
            picks = []
            
            for item in response.get("Items", []):
                parts = item["SK"].split("#")
                if len(parts) >= 3:
                    person_id = "#".join(parts[2:])
                    if "PersonID" in item:
                        person_id = item["PersonID"]
                    
                    picks.append({
                        "person_id": person_id,
                        "year": int(parts[1]),
                        "timestamp": item.get("Timestamp"),
                    })
            
            all_picks[player_id] = picks
        
        total_picks = sum(len(picks) for picks in all_picks.values())
        print(f"   ✓ Batch get player picks successful: {total_picks} total picks")
        
        # Collect unique person IDs
        person_ids = set()
        for picks in all_picks.values():
            person_ids.update(pick["person_id"] for pick in picks)
        
        print(f"   ✓ Unique person IDs collected: {len(person_ids)} people")
        
        # Test batch get people
        if person_ids:
            person_keys = [
                {"PK": f"PERSON#{pid}", "SK": "DETAILS"}
                for pid in list(person_ids)[:25]  # Test first 25
            ]
            
            response = dynamodb.batch_get_item(
                RequestItems={
                    'Deadpool': {
                        'Keys': person_keys,
                        'ConsistentRead': True
                    }
                }
            )
            
            people = response['Responses']['Deadpool']
            print(f"   ✓ Batch get people successful: {len(people)} people retrieved")
        
    except Exception as e:
        print(f"   ❌ Picks service flow failed: {e}")
        print(f"   Error details: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Check for specific issues
    print("\n3. Checking for specific issues...")
    
    # Check if there are any problematic person IDs
    problematic_picks = []
    for player_id, picks in all_picks.items():
        for pick in picks:
            person_id = pick["person_id"]
            # Check if person exists
            try:
                response = table.get_item(
                    Key={"PK": f"PERSON#{person_id}", "SK": "DETAILS"}
                )
                if not response.get("Item"):
                    problematic_picks.append({
                        "player_id": player_id,
                        "person_id": person_id,
                        "issue": "Person not found"
                    })
            except Exception as e:
                problematic_picks.append({
                    "player_id": player_id,
                    "person_id": person_id,
                    "issue": f"Error accessing person: {e}"
                })
    
    if problematic_picks:
        print(f"   ❌ Found {len(problematic_picks)} problematic picks:")
        for issue in problematic_picks[:5]:  # Show first 5
            print(f"     Player {issue['player_id']}: {issue['issue']} (Person: {issue['person_id']})")
    else:
        print("   ✓ No problematic picks found")
    
    print("\n=== CONCLUSION ===")
    print("The data flow that works for players endpoint should also work for picks endpoint.")
    print("If picks endpoint is still failing, the issue might be:")
    print("1. Exception handling in the picks service")
    print("2. Cache-related issues")
    print("3. Response formatting problems")
    print("4. Timeout issues with large data sets")

if __name__ == "__main__":
    debug_picks_vs_players()