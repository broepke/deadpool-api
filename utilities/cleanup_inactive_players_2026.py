#!/usr/bin/env python3
"""
Cleanup Inactive Players from 2026 Draft Order

This script removes players who have 0 picks from the 2026 draft order
and adjusts the remaining draft positions accordingly.

Players to remove:
- Brian Schanen (0 picks)
- Luke Marble (0 picks) 
- Robert Kennedy (0 picks)

Usage:
    python utilities/cleanup_inactive_players_2026.py [--dry-run] [--verbose]
"""

import boto3
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any


class InactivePlayerCleanup:
    def __init__(self, table_name: str = "Deadpool", dry_run: bool = False, verbose: bool = False):
        self.table_name = table_name
        self.dry_run = dry_run
        self.verbose = verbose
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
        # Players to remove (those with 0 picks)
        self.inactive_players = {
            'b4682458-6011-7019-f3e2-60c89d3ee00f': 'Brian Schanen',
            '2498f4b8-b061-70b9-1c42-84ceae3b40eb': 'Luke Marble', 
            '049864b8-1081-7020-7ec9-02f2c836277c': 'Robert Kennedy'
        }

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        
        if level == "ERROR":
            print(f"{prefix} {message}", file=sys.stderr)
        elif self.verbose or level in ["ERROR", "WARN"]:
            print(f"{prefix} {message}")

    def get_2026_draft_order(self) -> List[Dict[str, Any]]:
        """Get current 2026 draft order"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ':pk': 'YEAR#2026',
                    ':sk_prefix': 'ORDER#'
                }
            )
            
            draft_orders = []
            for item in response['Items']:
                # SK format: ORDER#{position}#PLAYER#{player_id}
                parts = item['SK'].split('#')
                if len(parts) >= 4:
                    position = int(parts[1])
                    player_id = parts[3]
                    draft_orders.append({
                        'position': position,
                        'player_id': player_id,
                        'sk': item['SK'],
                        'item': item
                    })
            
            # Sort by position
            draft_orders.sort(key=lambda x: x['position'])
            return draft_orders
            
        except Exception as e:
            self.log(f"Error getting 2026 draft order: {str(e)}", "ERROR")
            raise

    def get_player_name(self, player_id: str) -> str:
        """Get player name for logging"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'PLAYER#{player_id}',
                    'SK': 'DETAILS'
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                first_name = item.get('FirstName', '')
                last_name = item.get('LastName', '')
                return f"{first_name} {last_name}".strip()
            
            return player_id
            
        except Exception as e:
            self.log(f"Error getting player name for {player_id}: {str(e)}", "ERROR")
            return player_id

    def remove_inactive_players(self) -> bool:
        """Remove inactive players from 2026 draft order"""
        self.log("Removing inactive players from 2026 draft order...")
        
        try:
            # Get current draft order
            draft_orders = self.get_2026_draft_order()
            
            # Identify items to delete and keep
            items_to_delete = []
            active_players = []
            
            for order in draft_orders:
                player_id = order['player_id']
                player_name = self.get_player_name(player_id)
                
                if player_id in self.inactive_players:
                    items_to_delete.append(order)
                    self.log(f"  Marking for removal: Position {order['position']} - {player_name}")
                else:
                    active_players.append(order)
                    self.log(f"  Keeping: Position {order['position']} - {player_name}")
            
            if not items_to_delete:
                self.log("No inactive players found in draft order")
                return True
            
            # Delete inactive player records
            if not self.dry_run:
                for item in items_to_delete:
                    self.table.delete_item(
                        Key={
                            'PK': 'YEAR#2026',
                            'SK': item['sk']
                        }
                    )
                    player_name = self.inactive_players.get(item['player_id'], item['player_id'])
                    self.log(f"  Deleted: {player_name} from position {item['position']}")
            else:
                self.log(f"  DRY RUN: Would delete {len(items_to_delete)} inactive players")
            
            # Reorder remaining players
            self.reorder_active_players(active_players)
            
            return True
            
        except Exception as e:
            self.log(f"Error removing inactive players: {str(e)}", "ERROR")
            return False

    def reorder_active_players(self, active_players: List[Dict[str, Any]]) -> bool:
        """Reorder active players to fill gaps left by removed players"""
        self.log("Reordering active players...")
        
        try:
            # Create new draft order items with sequential positions
            new_items = []
            for new_position, player_order in enumerate(active_players, 1):
                player_id = player_order['player_id']
                player_name = self.get_player_name(player_id)
                
                new_item = {
                    'PK': 'YEAR#2026',
                    'SK': f'ORDER#{new_position:02d}#PLAYER#{player_id}',
                    'Type': 'DraftOrder',
                    'Year': 2026,
                    'DraftOrder': new_position,
                    'PlayerID': player_id
                }
                
                new_items.append(new_item)
                self.log(f"  New position {new_position}: {player_name}")
            
            if not self.dry_run:
                # Batch write new items
                with self.table.batch_writer() as batch:
                    for item in new_items:
                        batch.put_item(Item=item)
                
                self.log(f"Successfully reordered {len(new_items)} active players")
            else:
                self.log(f"DRY RUN: Would reorder {len(new_items)} active players")
            
            return True
            
        except Exception as e:
            self.log(f"Error reordering players: {str(e)}", "ERROR")
            return False

    def remove_draft_slots_records(self) -> bool:
        """Remove draft slots records for inactive players"""
        self.log("Removing draft slots records for inactive players...")
        
        try:
            for player_id, player_name in self.inactive_players.items():
                if not self.dry_run:
                    try:
                        self.table.delete_item(
                            Key={
                                'PK': f'PLAYER#{player_id}',
                                'SK': 'DRAFT_SLOTS#2026'
                            }
                        )
                        self.log(f"  Deleted draft slots record for {player_name}")
                    except Exception as e:
                        # It's okay if the record doesn't exist
                        self.log(f"  No draft slots record found for {player_name}")
                else:
                    self.log(f"  DRY RUN: Would delete draft slots record for {player_name}")
            
            return True
            
        except Exception as e:
            self.log(f"Error removing draft slots records: {str(e)}", "ERROR")
            return False

    def run_cleanup(self) -> bool:
        """Execute the complete cleanup process"""
        self.log("Starting inactive player cleanup for 2026...")
        
        if self.dry_run:
            self.log("*** DRY RUN MODE - No changes will be made ***")
        
        try:
            # Step 1: Remove inactive players from draft order and reorder
            if not self.remove_inactive_players():
                return False
            
            # Step 2: Remove draft slots records
            if not self.remove_draft_slots_records():
                return False
            
            self.log("✓ Cleanup completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Cleanup failed: {str(e)}", "ERROR")
            return False

    def print_final_draft_order(self):
        """Print the final draft order after cleanup"""
        try:
            draft_orders = self.get_2026_draft_order()
            
            self.log("=" * 50)
            self.log("FINAL 2026 DRAFT ORDER")
            self.log("=" * 50)
            
            for order in draft_orders:
                player_name = self.get_player_name(order['player_id'])
                self.log(f"  Position {order['position']}: {player_name}")
            
            self.log(f"\nTotal active players: {len(draft_orders)}")
            
        except Exception as e:
            self.log(f"Error printing final draft order: {str(e)}", "ERROR")


def main():
    parser = argparse.ArgumentParser(description='Cleanup inactive players from 2026 draft order')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool',
                       help='DynamoDB table name (default: Deadpool)')
    
    args = parser.parse_args()
    
    # Create cleanup instance
    cleanup = InactivePlayerCleanup(
        table_name=args.table_name,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    # Run cleanup
    success = cleanup.run_cleanup()
    
    # Print final draft order
    if success and not args.dry_run:
        cleanup.print_final_draft_order()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()