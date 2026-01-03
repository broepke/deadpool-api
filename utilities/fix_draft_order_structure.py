#!/usr/bin/env python3
"""
Fix 2026 Draft Order Structure

This script fixes the 2026 draft order structure by:
1. Removing all existing 2026 draft orders
2. Recreating them properly from the 2025 template
3. Ensuring we have exactly one record per player
"""

import boto3
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any


class DraftOrderFixer:
    def __init__(self, table_name: str = "Deadpool", verbose: bool = False, dry_run: bool = False):
        self.table_name = table_name
        self.verbose = verbose
        self.dry_run = dry_run
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

    def get_all_players(self) -> List[Dict[str, Any]]:
        """Get all players"""
        try:
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
                ExpressionAttributeValues={
                    ':pk_prefix': 'PLAYER#',
                    ':sk': 'DETAILS'
                }
            )
            
            players = []
            for item in response['Items']:
                player_id = item['PK'].replace('PLAYER#', '')
                players.append({
                    'id': player_id,
                    'name': f"{item.get('FirstName', '')} {item.get('LastName', '')}".strip()
                })
            
            return players
            
        except Exception as e:
            self.log(f"Error getting players: {str(e)}", "ERROR")
            return []

    def get_2025_draft_order(self) -> List[Dict[str, Any]]:
        """Get 2025 draft order as template"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={':pk': 'YEAR#2025'}
            )
            return response.get('Items', [])
        except Exception as e:
            self.log(f"Error getting 2025 draft order: {str(e)}", "ERROR")
            return []

    def delete_all_2026_draft_orders(self) -> bool:
        """Delete all existing 2026 draft order records"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={':pk': 'YEAR#2026'}
            )
            
            existing_orders = response.get('Items', [])
            if not existing_orders:
                self.log("No existing 2026 draft orders to delete")
                return True
            
            self.log(f"Deleting {len(existing_orders)} existing 2026 draft order records")
            
            if self.dry_run:
                self.log("DRY RUN: Would delete existing 2026 draft orders")
                return True
            
            # Delete all existing 2026 draft orders
            with self.table.batch_writer() as batch:
                for order in existing_orders:
                    batch.delete_item(
                        Key={
                            'PK': order['PK'],
                            'SK': order['SK']
                        }
                    )
            
            self.log(f"✓ Deleted {len(existing_orders)} existing records")
            return True
            
        except Exception as e:
            self.log(f"Error deleting 2026 draft orders: {str(e)}", "ERROR")
            return False

    def create_proper_2026_draft_order(self) -> bool:
        """Create proper 2026 draft order from 2025 template"""
        try:
            # Get 2025 template
            draft_orders_2025 = self.get_2025_draft_order()
            if not draft_orders_2025:
                self.log("No 2025 draft order found to copy from", "ERROR")
                return False
            
            # Get all players to ensure we have the right count
            all_players = self.get_all_players()
            self.log(f"Found {len(all_players)} total players")
            self.log(f"Found {len(draft_orders_2025)} 2025 draft order records")
            
            if len(draft_orders_2025) < len(all_players):
                self.log(f"Warning: 2025 has fewer draft orders ({len(draft_orders_2025)}) than total players ({len(all_players)})", "WARN")
            
            if self.dry_run:
                self.log(f"DRY RUN: Would create {len(draft_orders_2025)} new 2026 draft order records")
                return True
            
            # Create new 2026 draft order records
            with self.table.batch_writer() as batch:
                for order in draft_orders_2025:
                    new_item = {
                        'PK': 'YEAR#2026',
                        'SK': order['SK'],  # Keep same SK format from 2025
                        'Year': 2026
                    }
                    
                    # Copy other fields if they exist
                    for field in ['PlayerID', 'DraftOrder']:
                        if field in order:
                            new_item[field] = order[field]
                    
                    batch.put_item(Item=new_item)
            
            self.log(f"✓ Created {len(draft_orders_2025)} new 2026 draft order records")
            return True
            
        except Exception as e:
            self.log(f"Error creating 2026 draft order: {str(e)}", "ERROR")
            return False

    def verify_fix(self) -> bool:
        """Verify the fix worked"""
        try:
            # Check final counts
            players = self.get_all_players()
            
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={':pk': 'YEAR#2026'}
            )
            draft_orders = response.get('Items', [])
            
            self.log(f"Final verification:")
            self.log(f"  Total players: {len(players)}")
            self.log(f"  2026 draft orders: {len(draft_orders)}")
            
            # Check for duplicates
            order_numbers = []
            for order in draft_orders:
                sk_parts = order['SK'].split('#')
                if len(sk_parts) >= 2:
                    order_num = int(sk_parts[1])
                    order_numbers.append(order_num)
            
            order_numbers.sort()
            unique_orders = list(set(order_numbers))
            
            self.log(f"  Draft order numbers: {order_numbers}")
            self.log(f"  Unique orders: {len(unique_orders)}")
            
            if len(order_numbers) == len(unique_orders):
                self.log("✓ No duplicate draft orders")
                return True
            else:
                self.log("✗ Still have duplicate draft orders", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error verifying fix: {str(e)}", "ERROR")
            return False

    def fix_draft_order_structure(self) -> bool:
        """Main method to fix the draft order structure"""
        self.log("Starting draft order structure fix...")
        
        # Step 1: Delete all existing 2026 draft orders
        if not self.delete_all_2026_draft_orders():
            return False
        
        # Step 2: Create proper 2026 draft order from 2025 template
        if not self.create_proper_2026_draft_order():
            return False
        
        # Step 3: Verify the fix
        if not self.dry_run:
            return self.verify_fix()
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Fix 2026 Draft Order Structure')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool', help='DynamoDB table name')
    
    args = parser.parse_args()
    
    fixer = DraftOrderFixer(
        table_name=args.table_name,
        verbose=args.verbose,
        dry_run=args.dry_run
    )
    
    try:
        success = fixer.fix_draft_order_structure()
        
        if success:
            if not args.dry_run:
                print("✓ Draft order structure fix completed successfully")
            else:
                print("✓ Dry run completed")
        else:
            print("✗ Draft order structure fix failed")
            sys.exit(1)
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()