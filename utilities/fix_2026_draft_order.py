#!/usr/bin/env python3
"""
Fix 2026 Draft Order

This script cleans up the 2026 draft order by:
1. Removing all existing 2026 draft order records
2. Creating a clean draft order with only active players (those with picks)

Usage:
    python utilities/fix_2026_draft_order.py [--dry-run] [--verbose]
"""

import boto3
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any


class DraftOrderFixer:
    def __init__(self, table_name: str = "Deadpool", dry_run: bool = False, verbose: bool = False):
        self.table_name = table_name
        self.dry_run = dry_run
        self.verbose = verbose
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        
        if level == "ERROR":
            print(f"{prefix} {message}", file=sys.stderr)
        elif self.verbose or level in ["ERROR", "WARN"]:
            print(f"{prefix} {message}")

    def get_all_2026_draft_records(self) -> List[Dict[str, Any]]:
        """Get all 2026 draft order records"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={
                    ':pk': 'YEAR#2026'
                }
            )
            
            return response.get('Items', [])
            
        except Exception as e:
            self.log(f"Error getting 2026 draft records: {str(e)}", "ERROR")
            raise

    def get_active_players_with_picks(self) -> List[Dict[str, Any]]:
        """Get players who have picks in 2026 (active players)"""
        try:
            # Scan for all 2026 picks
            response = self.table.scan(
                FilterExpression="begins_with(SK, :pick_prefix)",
                ExpressionAttributeValues={
                    ':pick_prefix': 'PICK#2026#'
                }
            )
            
            # Extract unique player IDs
            player_ids = set()
            for item in response.get('Items', []):
                # PK format: PLAYER#{player_id}
                player_id = item['PK'].replace('PLAYER#', '')
                player_ids.add(player_id)
            
            # Get player details
            active_players = []
            for player_id in player_ids:
                try:
                    player_response = self.table.get_item(
                        Key={
                            'PK': f'PLAYER#{player_id}',
                            'SK': 'DETAILS'
                        }
                    )
                    
                    if 'Item' in player_response:
                        item = player_response['Item']
                        first_name = item.get('FirstName', '')
                        last_name = item.get('LastName', '')
                        name = f"{first_name} {last_name}".strip()
                        
                        active_players.append({
                            'id': player_id,
                            'name': name,
                            'first_name': first_name,
                            'last_name': last_name
                        })
                        
                except Exception as e:
                    self.log(f"Error getting player {player_id}: {str(e)}", "ERROR")
            
            # Sort by name for consistent ordering
            active_players.sort(key=lambda x: x['name'])
            
            self.log(f"Found {len(active_players)} active players with 2026 picks")
            for player in active_players:
                self.log(f"  - {player['name']}")
            
            return active_players
            
        except Exception as e:
            self.log(f"Error getting active players: {str(e)}", "ERROR")
            raise

    def get_2025_final_standings(self, active_players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate 2025 final standings for active players only"""
        try:
            self.log("Calculating 2025 final standings for active players...")
            
            leaderboard = []
            for player in active_players:
                player_id = player['id']
                player_name = player['name']
                
                # Get 2025 picks
                picks_response = self.table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                    ExpressionAttributeValues={
                        ':pk': f'PLAYER#{player_id}',
                        ':sk_prefix': 'PICK#2025#'
                    }
                )
                
                # Calculate 2025 score
                total_score = 0
                for pick_item in picks_response.get('Items', []):
                    # Extract person_id from SK: PICK#2025#person_id
                    person_id = pick_item['SK'].split('#')[2]
                    
                    # Get person details
                    person_response = self.table.get_item(
                        Key={
                            'PK': f'PERSON#{person_id}',
                            'SK': 'DETAILS'
                        }
                    )
                    
                    if 'Item' in person_response:
                        person = person_response['Item']
                        death_date = person.get('DeathDate')
                        
                        if death_date and death_date.startswith('2025'):
                            age = person.get('Age', 0)
                            score = 50 + (100 - age)
                            total_score += score
                
                leaderboard.append({
                    'player_id': player_id,
                    'player_name': player_name,
                    'score': total_score
                })
            
            # Sort by score (highest first)
            leaderboard.sort(key=lambda x: x['score'], reverse=True)
            
            self.log("2025 Final Standings (Active Players Only):")
            for i, entry in enumerate(leaderboard, 1):
                self.log(f"  {i}. {entry['player_name']}: {entry['score']} points")
            
            return leaderboard
            
        except Exception as e:
            self.log(f"Error calculating 2025 standings: {str(e)}", "ERROR")
            raise

    def clear_all_2026_draft_records(self) -> bool:
        """Remove all existing 2026 draft order records"""
        try:
            self.log("Clearing all existing 2026 draft order records...")
            
            # Get all 2026 records
            records = self.get_all_2026_draft_records()
            
            if not records:
                self.log("No existing 2026 draft records found")
                return True
            
            self.log(f"Found {len(records)} existing 2026 records to delete")
            
            if not self.dry_run:
                # Delete all records
                for record in records:
                    self.table.delete_item(
                        Key={
                            'PK': record['PK'],
                            'SK': record['SK']
                        }
                    )
                
                self.log(f"Deleted {len(records)} existing 2026 draft records")
            else:
                self.log(f"DRY RUN: Would delete {len(records)} existing 2026 draft records")
            
            return True
            
        except Exception as e:
            self.log(f"Error clearing 2026 draft records: {str(e)}", "ERROR")
            return False

    def create_clean_2026_draft_order(self, leaderboard: List[Dict[str, Any]]) -> bool:
        """Create clean 2026 draft order based on reverse 2025 standings"""
        try:
            self.log("Creating clean 2026 draft order...")
            
            # Reverse the leaderboard (worst performing player gets first pick)
            reversed_leaderboard = list(reversed(leaderboard))
            
            draft_order_items = []
            for position, entry in enumerate(reversed_leaderboard, 1):
                player_id = entry['player_id']
                player_name = entry['player_name']
                
                item = {
                    'PK': 'YEAR#2026',
                    'SK': f'ORDER#{position:02d}#PLAYER#{player_id}',
                    'Type': 'DraftOrder',
                    'Year': 2026,
                    'DraftOrder': position,
                    'PlayerID': player_id
                }
                
                draft_order_items.append(item)
                self.log(f"  Position {position}: {player_name} (2025 score: {entry['score']})")
            
            if not self.dry_run:
                # Batch write the draft order items
                with self.table.batch_writer() as batch:
                    for item in draft_order_items:
                        batch.put_item(Item=item)
                
                self.log(f"Successfully created clean 2026 draft order for {len(draft_order_items)} players")
            else:
                self.log(f"DRY RUN: Would create clean 2026 draft order for {len(draft_order_items)} players")
            
            return True
            
        except Exception as e:
            self.log(f"Error creating clean 2026 draft order: {str(e)}", "ERROR")
            return False

    def run_fix(self) -> bool:
        """Execute the complete fix process"""
        self.log("Starting 2026 draft order fix...")
        
        if self.dry_run:
            self.log("*** DRY RUN MODE - No changes will be made ***")
        
        try:
            # Step 1: Get active players (those with 2026 picks)
            active_players = self.get_active_players_with_picks()
            
            if not active_players:
                self.log("No active players found with 2026 picks", "ERROR")
                return False
            
            # Step 2: Calculate 2025 final standings for active players
            leaderboard = self.get_2025_final_standings(active_players)
            
            # Step 3: Clear all existing 2026 draft records
            if not self.clear_all_2026_draft_records():
                return False
            
            # Step 4: Create clean 2026 draft order
            if not self.create_clean_2026_draft_order(leaderboard):
                return False
            
            self.log("✓ Draft order fix completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Draft order fix failed: {str(e)}", "ERROR")
            return False

    def print_final_draft_order(self):
        """Print the final draft order after fix"""
        try:
            records = self.get_all_2026_draft_records()
            
            # Filter and sort draft order records
            draft_orders = []
            for record in records:
                if record['SK'].startswith('ORDER#'):
                    parts = record['SK'].split('#')
                    if len(parts) >= 4:
                        position = int(parts[1])
                        player_id = parts[3]
                        draft_orders.append({
                            'position': position,
                            'player_id': player_id
                        })
            
            draft_orders.sort(key=lambda x: x['position'])
            
            self.log("=" * 50)
            self.log("FINAL 2026 DRAFT ORDER")
            self.log("=" * 50)
            
            for order in draft_orders:
                # Get player name
                try:
                    player_response = self.table.get_item(
                        Key={
                            'PK': f'PLAYER#{order["player_id"]}',
                            'SK': 'DETAILS'
                        }
                    )
                    
                    if 'Item' in player_response:
                        item = player_response['Item']
                        first_name = item.get('FirstName', '')
                        last_name = item.get('LastName', '')
                        name = f"{first_name} {last_name}".strip()
                    else:
                        name = order['player_id']
                        
                except Exception:
                    name = order['player_id']
                
                self.log(f"  Position {order['position']}: {name}")
            
            self.log(f"\nTotal active players: {len(draft_orders)}")
            
        except Exception as e:
            self.log(f"Error printing final draft order: {str(e)}", "ERROR")


def main():
    parser = argparse.ArgumentParser(description='Fix 2026 draft order')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool',
                       help='DynamoDB table name (default: Deadpool)')
    
    args = parser.parse_args()
    
    # Create fixer instance
    fixer = DraftOrderFixer(
        table_name=args.table_name,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    # Run fix
    success = fixer.run_fix()
    
    # Print final draft order
    if success and not args.dry_run:
        fixer.print_final_draft_order()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()