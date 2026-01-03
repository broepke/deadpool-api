#!/usr/bin/env python3
"""
Fix 2026 API Issues Script

This script addresses the API issues discovered after the 2026 migration:
1. Ensures 2026 draft order records exist
2. Clears problematic caches
3. Validates 2026 data integrity
4. Provides fallback year handling

Usage:
    python utilities/fix_2026_api_issues.py [--dry-run] [--verbose]
"""

import boto3
import argparse
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError


class API2026Fixer:
    def __init__(self, table_name: str = "Deadpool", verbose: bool = False, dry_run: bool = False):
        self.table_name = table_name
        self.verbose = verbose
        self.dry_run = dry_run
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
        self.issues_found = []
        self.fixes_applied = []

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        
        if level == "ERROR":
            print(f"{prefix} {message}", file=sys.stderr)
        elif self.verbose or level in ["ERROR", "WARN"]:
            print(f"{prefix} {message}")

    def get_all_players(self) -> List[Dict[str, Any]]:
        """Get all active players"""
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
                    'name': f"{item.get('FirstName', '')} {item.get('LastName', '')}".strip(),
                    'first_name': item.get('FirstName', ''),
                    'last_name': item.get('LastName', '')
                })
            
            return players
            
        except Exception as e:
            self.log(f"Error getting players: {str(e)}", "ERROR")
            raise

    def check_2026_draft_order(self) -> bool:
        """Check if 2026 draft order exists"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={':pk': 'YEAR#2026'}
            )
            
            draft_orders = response.get('Items', [])
            players = self.get_all_players()
            
            if len(draft_orders) == 0:
                self.issues_found.append("No 2026 draft order records found")
                return False
            elif len(draft_orders) != len(players):
                self.issues_found.append(f"2026 draft order incomplete: {len(draft_orders)} records, {len(players)} players")
                return False
            
            self.log(f"✓ 2026 draft order exists with {len(draft_orders)} records")
            return True
            
        except Exception as e:
            self.log(f"Error checking 2026 draft order: {str(e)}", "ERROR")
            self.issues_found.append(f"Error checking 2026 draft order: {str(e)}")
            return False

    def create_2026_draft_order(self) -> bool:
        """Create 2026 draft order based on 2025 order"""
        try:
            if self.dry_run:
                self.log("DRY RUN: Would create 2026 draft order")
                return True
            
            # Get 2025 draft order as template
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={':pk': 'YEAR#2025'}
            )
            
            draft_orders_2025 = response.get('Items', [])
            if not draft_orders_2025:
                self.log("No 2025 draft order found to copy from", "ERROR")
                return False
            
            # Create 2026 draft order records
            with self.table.batch_writer() as batch:
                for order in draft_orders_2025:
                    # Extract player ID from SK format: ORDER#{draft_order}#PLAYER#{player_id}
                    sk_parts = order['SK'].split('#')
                    if len(sk_parts) >= 4:
                        player_id = sk_parts[3]
                        draft_order = int(sk_parts[1])
                        
                        new_item = {
                            'PK': 'YEAR#2026',
                            'SK': order['SK'],  # Keep same SK format
                            'Year': 2026,
                            'CreatedAt': datetime.now().isoformat()
                        }
                        
                        # Add optional fields if they exist in the source
                        if 'PlayerID' in order:
                            new_item['PlayerID'] = order['PlayerID']
                        if 'DraftOrder' in order:
                            new_item['DraftOrder'] = order['DraftOrder']
                        else:
                            new_item['DraftOrder'] = draft_order
                            
                        batch.put_item(Item=new_item)
            
            self.fixes_applied.append(f"Created 2026 draft order with {len(draft_orders_2025)} records")
            self.log(f"✓ Created 2026 draft order with {len(draft_orders_2025)} records")
            return True
            
        except Exception as e:
            self.log(f"Error creating 2026 draft order: {str(e)}", "ERROR")
            return False

    def check_migration_metadata(self) -> bool:
        """Check if migration metadata exists"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': 'MIGRATION#2025_TO_2026',
                    'SK': 'METADATA'
                }
            )
            
            if 'Item' not in response:
                self.issues_found.append("Migration metadata not found")
                return False
            
            metadata = response['Item']
            status = metadata.get('Status', '')
            
            if status not in ['COMPLETED', 'COMPLETED_WITH_ERRORS']:
                self.issues_found.append(f"Migration status is '{status}', expected COMPLETED")
                return False
            
            self.log(f"✓ Migration metadata found with status: {status}")
            return True
            
        except Exception as e:
            self.log(f"Error checking migration metadata: {str(e)}", "ERROR")
            self.issues_found.append(f"Error checking migration metadata: {str(e)}")
            return False

    def validate_2026_picks_exist(self) -> bool:
        """Validate that 2026 picks exist for players"""
        try:
            players = self.get_all_players()
            players_with_picks = 0
            total_picks = 0
            
            for player in players:
                response = self.table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                    ExpressionAttributeValues={
                        ':pk': f'PLAYER#{player["id"]}',
                        ':sk_prefix': 'PICK#2026#'
                    }
                )
                
                picks = response.get('Items', [])
                if picks:
                    players_with_picks += 1
                    total_picks += len(picks)
            
            if players_with_picks == 0:
                self.issues_found.append("No players have 2026 picks")
                return False
            
            self.log(f"✓ {players_with_picks}/{len(players)} players have 2026 picks ({total_picks} total)")
            return True
            
        except Exception as e:
            self.log(f"Error validating 2026 picks: {str(e)}", "ERROR")
            self.issues_found.append(f"Error validating 2026 picks: {str(e)}")
            return False

    def clear_problematic_caches(self) -> bool:
        """Clear cache entries that might be causing issues"""
        try:
            if self.dry_run:
                self.log("DRY RUN: Would clear problematic cache entries")
                return True
            
            # Note: This would require access to the cache system
            # For now, we'll create a record to indicate cache should be cleared
            cache_clear_record = {
                'PK': 'SYSTEM#CACHE_CLEAR',
                'SK': f'REQUEST#{datetime.now().isoformat()}',
                'RequestedAt': datetime.now().isoformat(),
                'Reason': '2026_API_ISSUES_FIX',
                'CacheKeys': [
                    'picks_list_2026_*',
                    'picks_counts_2026',
                    'leaderboard_2026',
                    'next_drafter_2026',
                    'person_picks_*_2026'
                ]
            }
            
            self.table.put_item(Item=cache_clear_record)
            self.fixes_applied.append("Created cache clear request record")
            self.log("✓ Created cache clear request record")
            return True
            
        except Exception as e:
            self.log(f"Error creating cache clear request: {str(e)}", "ERROR")
            return False

    def create_api_fallback_config(self) -> bool:
        """Create configuration for API fallback behavior"""
        try:
            if self.dry_run:
                self.log("DRY RUN: Would create API fallback configuration")
                return True
            
            fallback_config = {
                'PK': 'CONFIG#API_FALLBACK',
                'SK': 'YEAR_HANDLING',
                'DefaultYear': 2025,  # Fallback to 2025 if 2026 has issues
                'EnableYearFallback': True,
                'FallbackReason': '2026_MIGRATION_ISSUES',
                'CreatedAt': datetime.now().isoformat(),
                'UpdatedAt': datetime.now().isoformat()
            }
            
            self.table.put_item(Item=fallback_config)
            self.fixes_applied.append("Created API fallback configuration")
            self.log("✓ Created API fallback configuration")
            return True
            
        except Exception as e:
            self.log(f"Error creating API fallback config: {str(e)}", "ERROR")
            return False

    def run_diagnostics(self) -> Dict[str, Any]:
        """Run comprehensive diagnostics"""
        self.log("Starting 2026 API diagnostics...")
        
        diagnostics = {
            'draft_order_2026': self.check_2026_draft_order(),
            'migration_metadata': self.check_migration_metadata(),
            'picks_2026': self.validate_2026_picks_exist()
        }
        
        self.log(f"Diagnostics complete. Issues found: {len(self.issues_found)}")
        return diagnostics

    def apply_fixes(self) -> bool:
        """Apply all necessary fixes"""
        self.log("Applying fixes for 2026 API issues...")
        
        success = True
        
        # Fix 1: Ensure 2026 draft order exists
        if not self.check_2026_draft_order():
            if not self.create_2026_draft_order():
                success = False
        
        # Fix 2: Clear problematic caches
        if not self.clear_problematic_caches():
            success = False
        
        # Fix 3: Create fallback configuration
        if not self.create_api_fallback_config():
            success = False
        
        self.log(f"Fixes complete. Applied {len(self.fixes_applied)} fixes.")
        return success

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report"""
        return {
            'timestamp': datetime.now().isoformat(),
            'table_name': self.table_name,
            'issues_found': self.issues_found,
            'fixes_applied': self.fixes_applied,
            'recommendations': [
                "Test the API endpoint after applying fixes",
                "Monitor CloudWatch logs for any remaining errors",
                "Consider implementing year parameter validation",
                "Add health checks for 2026 data integrity"
            ]
        }


def main():
    parser = argparse.ArgumentParser(description='Fix 2026 API Issues')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool', help='DynamoDB table name')
    
    args = parser.parse_args()
    
    fixer = API2026Fixer(
        table_name=args.table_name,
        verbose=args.verbose,
        dry_run=args.dry_run
    )
    
    try:
        # Run diagnostics
        diagnostics = fixer.run_diagnostics()
        
        # Apply fixes if issues found
        if fixer.issues_found:
            print(f"\nFound {len(fixer.issues_found)} issues:")
            for issue in fixer.issues_found:
                print(f"  - {issue}")
            
            if not args.dry_run:
                print("\nApplying fixes...")
                success = fixer.apply_fixes()
                
                if success:
                    print("✓ All fixes applied successfully")
                else:
                    print("✗ Some fixes failed")
                    sys.exit(1)
            else:
                print("\nDry run complete. Use --verbose to see what would be done.")
        else:
            print("✓ No issues found")
        
        # Generate report
        report = fixer.generate_report()
        
        if args.verbose:
            print("\n" + "="*50)
            print("DETAILED REPORT")
            print("="*50)
            print(json.dumps(report, indent=2))
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()