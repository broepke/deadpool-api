#!/usr/bin/env python3
"""
Cleanup Duplicate 2026 Draft Orders Script

This script removes duplicate 2026 draft order records that were created
during the API fix process, keeping only the original records.
"""

import boto3
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any
from botocore.exceptions import ClientError


class DraftOrderCleaner:
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

    def get_2026_draft_orders(self) -> List[Dict[str, Any]]:
        """Get all 2026 draft order records"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={':pk': 'YEAR#2026'}
            )
            return response.get('Items', [])
        except Exception as e:
            self.log(f"Error getting 2026 draft orders: {str(e)}", "ERROR")
            return []

    def analyze_duplicates(self, draft_orders: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze draft orders to find duplicates by SK"""
        sk_groups = {}
        for order in draft_orders:
            sk = order['SK']
            if sk not in sk_groups:
                sk_groups[sk] = []
            sk_groups[sk].append(order)
        
        return sk_groups

    def cleanup_duplicates(self) -> bool:
        """Remove duplicate 2026 draft order records"""
        try:
            # Get all 2026 draft orders
            draft_orders = self.get_2026_draft_orders()
            self.log(f"Found {len(draft_orders)} total 2026 draft order records")
            
            if not draft_orders:
                self.log("No 2026 draft orders found")
                return True
            
            # Analyze duplicates
            sk_groups = self.analyze_duplicates(draft_orders)
            duplicates_found = 0
            records_to_delete = []
            
            for sk, records in sk_groups.items():
                if len(records) > 1:
                    duplicates_found += len(records) - 1
                    # Keep the oldest record (without CreatedAt or with earliest CreatedAt)
                    records_sorted = sorted(records, key=lambda x: x.get('CreatedAt', '1900-01-01'))
                    keep_record = records_sorted[0]
                    delete_records = records_sorted[1:]
                    
                    self.log(f"SK {sk}: Keeping 1 record, marking {len(delete_records)} for deletion")
                    records_to_delete.extend(delete_records)
            
            if duplicates_found == 0:
                self.log("No duplicate records found")
                return True
            
            self.log(f"Found {duplicates_found} duplicate records to remove")
            
            if self.dry_run:
                self.log("DRY RUN: Would delete the following records:")
                for record in records_to_delete:
                    self.log(f"  - PK: {record['PK']}, SK: {record['SK']}")
                return True
            
            # Delete duplicate records
            deleted_count = 0
            with self.table.batch_writer() as batch:
                for record in records_to_delete:
                    batch.delete_item(
                        Key={
                            'PK': record['PK'],
                            'SK': record['SK']
                        }
                    )
                    deleted_count += 1
            
            self.log(f"✓ Successfully deleted {deleted_count} duplicate records")
            
            # Verify final count
            final_orders = self.get_2026_draft_orders()
            self.log(f"Final count: {len(final_orders)} draft order records")
            
            return True
            
        except Exception as e:
            self.log(f"Error cleaning up duplicates: {str(e)}", "ERROR")
            return False

    def verify_players_working(self) -> bool:
        """Verify that players endpoint is working after cleanup"""
        try:
            # This would require making an API call, but for now we'll just
            # verify the draft order count matches expected players
            draft_orders = self.get_2026_draft_orders()
            
            # Get total players
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
                ExpressionAttributeValues={
                    ':pk_prefix': 'PLAYER#',
                    ':sk': 'DETAILS'
                }
            )
            total_players = len(response.get('Items', []))
            
            self.log(f"Draft orders: {len(draft_orders)}, Total players: {total_players}")
            
            if len(draft_orders) == total_players:
                self.log("✓ Draft order count matches player count")
                return True
            else:
                self.log(f"⚠ Draft order count ({len(draft_orders)}) doesn't match player count ({total_players})", "WARN")
                return False
                
        except Exception as e:
            self.log(f"Error verifying players: {str(e)}", "ERROR")
            return False


def main():
    parser = argparse.ArgumentParser(description='Cleanup Duplicate 2026 Draft Orders')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool', help='DynamoDB table name')
    
    args = parser.parse_args()
    
    cleaner = DraftOrderCleaner(
        table_name=args.table_name,
        verbose=args.verbose,
        dry_run=args.dry_run
    )
    
    try:
        print("Starting cleanup of duplicate 2026 draft orders...")
        
        success = cleaner.cleanup_duplicates()
        
        if success:
            if not args.dry_run:
                print("✓ Cleanup completed successfully")
                cleaner.verify_players_working()
            else:
                print("✓ Dry run completed")
        else:
            print("✗ Cleanup failed")
            sys.exit(1)
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()