#!/usr/bin/env python3
"""
Debug script to validate 2026 picks API diagnosis
"""
import boto3
import json
from datetime import datetime

def check_2026_data():
    """Check the current state of 2026 data"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Deadpool')
    
    print("=== 2026 API Debug Analysis ===\n")
    
    # 1. Check 2026 draft order
    print("1. Checking 2026 draft order...")
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={':pk': 'YEAR#2026'}
        )
        draft_orders = response.get('Items', [])
        print(f"   Found {len(draft_orders)} draft order records for 2026")
        
        if draft_orders:
            print("   Draft order details:")
            for order in sorted(draft_orders, key=lambda x: int(x['SK'].split('#')[1])):
                parts = order['SK'].split('#')
                if len(parts) >= 4:
                    draft_pos = parts[1]
                    player_id = parts[3]
                    print(f"     Position {draft_pos}: Player {player_id}")
        else:
            print("   ❌ NO 2026 DRAFT ORDER FOUND - This is the primary issue!")
            
    except Exception as e:
        print(f"   ❌ Error checking draft order: {e}")
    
    # 2. Check total players
    print("\n2. Checking total active players...")
    try:
        response = table.scan(
            FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
            ExpressionAttributeValues={
                ':pk_prefix': 'PLAYER#',
                ':sk': 'DETAILS'
            }
        )
        players = response['Items']
        print(f"   Found {len(players)} total players in system")
        
        if len(draft_orders) < len(players):
            missing = len(players) - len(draft_orders)
            print(f"   ❌ Missing {missing} players from 2026 draft order")
            
    except Exception as e:
        print(f"   ❌ Error checking players: {e}")
    
    # 3. Check 2026 picks data
    print("\n3. Checking 2026 picks data...")
    try:
        response = table.scan(
            FilterExpression="begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={':sk_prefix': 'PICK#2026#'}
        )
        picks_2026 = response['Items']
        print(f"   Found {len(picks_2026)} picks for 2026")
        
        if picks_2026:
            print("   ✓ 2026 picks data exists")
        else:
            print("   ⚠️  No 2026 picks found")
            
    except Exception as e:
        print(f"   ❌ Error checking picks: {e}")
    
    # 4. Check 2025 data for comparison
    print("\n4. Checking 2025 data for comparison...")
    try:
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={':pk': 'YEAR#2025'}
        )
        draft_orders_2025 = response.get('Items', [])
        print(f"   Found {len(draft_orders_2025)} draft order records for 2025")
        
        if len(draft_orders_2025) > len(draft_orders):
            print(f"   ✓ 2025 has complete draft order ({len(draft_orders_2025)} vs {len(draft_orders)})")
            
    except Exception as e:
        print(f"   ❌ Error checking 2025 data: {e}")
    
    print("\n=== DIAGNOSIS SUMMARY ===")
    if len(draft_orders) == 0:
        print("❌ PRIMARY ISSUE: No 2026 draft order records exist")
        print("   This causes get_players(2026) to return empty list")
        print("   Which makes the picks API fail with 500 error")
    elif len(draft_orders) < len(players):
        print("❌ PRIMARY ISSUE: Incomplete 2026 draft order")
        print(f"   Only {len(draft_orders)} of {len(players)} players have 2026 draft positions")
        print("   This causes partial data and API inconsistencies")
    else:
        print("✓ 2026 draft order appears complete")
        print("   Issue may be elsewhere in the API chain")
    
    print("\n=== RECOMMENDED FIX ===")
    print("1. Run: python utilities/fix_2026_api_issues.py --verbose")
    print("2. This will create missing 2026 draft order records")
    print("3. Test the API endpoint again")

if __name__ == "__main__":
    check_2026_data()