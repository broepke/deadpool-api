#!/usr/bin/env python3
"""
Deadpool Game 2025 to 2026 Migration Script

This script migrates all 2025 player picks to 2026 while preserving the exact same
celebrity selections but resetting the scoring period for the new year.

Usage:
    python utilities/migrate_2025_to_2026.py [--dry-run] [--verbose]

Options:
    --dry-run    Show what would be done without making changes
    --verbose    Show detailed progress information
"""

import boto3
import json
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any, Tuple
from botocore.exceptions import ClientError


class DeadpoolMigration:
    def __init__(self, table_name: str = "Deadpool", dry_run: bool = False, verbose: bool = False):
        self.table_name = table_name
        self.dry_run = dry_run
        self.verbose = verbose
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
        # Migration timestamp
        self.migration_timestamp = "2026-01-01T00:00:00.000Z"
        
        # Statistics
        self.stats = {
            'players_processed': 0,
            'picks_migrated': 0,
            'draft_orders_created': 0,
            'errors': []
        }

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        
        if level == "ERROR":
            print(f"{prefix} {message}", file=sys.stderr)
        elif self.verbose or level in ["ERROR", "WARN"]:
            print(f"{prefix} {message}")

    def get_2025_leaderboard(self) -> List[Dict[str, Any]]:
        """Get final 2025 leaderboard to determine 2026 draft order"""
        self.log("Calculating 2025 final leaderboard...")
        
        try:
            # Get all players
            players = self.get_all_players()
            
            # Get all 2025 picks for each player
            leaderboard = []
            for player in players:
                player_id = player['id']
                picks = self.get_player_picks(player_id, 2025)
                
                # Calculate 2025 score
                total_score = 0
                for pick in picks:
                    person = self.get_person(pick['person_id'])
                    if person and person.get('death_date'):
                        # Check if death was in 2025
                        death_year = int(person['death_date'][:4])
                        if death_year == 2025:
                            age = person.get('age', 0)
                            score = 50 + (100 - age)
                            total_score += score
                
                leaderboard.append({
                    'player_id': player_id,
                    'player_name': player['name'],
                    'score': total_score,
                    'pick_count': len(picks)
                })
            
            # Sort by score (highest first)
            leaderboard.sort(key=lambda x: x['score'], reverse=True)
            
            self.log(f"2025 Final Leaderboard:")
            for i, entry in enumerate(leaderboard, 1):
                self.log(f"  {i}. {entry['player_name']}: {entry['score']} points ({entry['pick_count']} picks)")
            
            return leaderboard
            
        except Exception as e:
            self.log(f"Error calculating 2025 leaderboard: {str(e)}", "ERROR")
            raise

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
                    'last_name': item.get('LastName', ''),
                    'phone_verified': item.get('PhoneVerified', False),
                    'sms_notifications_enabled': item.get('SmsNotificationsEnabled', False)
                })
            
            self.log(f"Found {len(players)} active players")
            return players
            
        except Exception as e:
            self.log(f"Error getting players: {str(e)}", "ERROR")
            raise

    def get_player_picks(self, player_id: str, year: int) -> List[Dict[str, Any]]:
        """Get all picks for a player in a specific year"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ':pk': f'PLAYER#{player_id}',
                    ':sk_prefix': f'PICK#{year}#'
                }
            )
            
            picks = []
            for item in response['Items']:
                # Extract person_id from SK: PICK#2025#person_id
                person_id = item['SK'].split('#')[2]
                picks.append({
                    'person_id': person_id,
                    'year': item.get('Year', year),
                    'timestamp': item.get('Timestamp', '')
                })
            
            return picks
            
        except Exception as e:
            self.log(f"Error getting picks for player {player_id}: {str(e)}", "ERROR")
            return []

    def get_person(self, person_id: str) -> Dict[str, Any]:
        """Get person details"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'PERSON#{person_id}',
                    'SK': 'DETAILS'
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'id': person_id,
                    'name': item.get('Name', ''),
                    'death_date': item.get('DeathDate'),
                    'age': item.get('Age', 0)
                }
            return None
            
        except Exception as e:
            self.log(f"Error getting person {person_id}: {str(e)}", "ERROR")
            return None

    def create_2026_draft_order(self, leaderboard: List[Dict[str, Any]]) -> bool:
        """Create 2026 draft order based on reverse 2025 standings"""
        self.log("Creating 2026 draft order...")
        
        try:
            # Reverse the leaderboard (worst performing player gets first pick)
            reversed_leaderboard = list(reversed(leaderboard))
            
            draft_order_items = []
            for position, entry in enumerate(reversed_leaderboard, 1):
                player_id = entry['player_id']
                
                item = {
                    'PK': 'YEAR#2026',
                    'SK': f'ORDER#{position:02d}#PLAYER#{player_id}',
                    'Type': 'DraftOrder',
                    'Year': 2026,
                    'DraftOrder': position,
                    'PlayerID': player_id
                }
                
                draft_order_items.append(item)
                self.log(f"  Draft position {position}: {entry['player_name']} (2025 score: {entry['score']})")
            
            if not self.dry_run:
                # Batch write the draft order items
                with self.table.batch_writer() as batch:
                    for item in draft_order_items:
                        batch.put_item(Item=item)
                
                self.stats['draft_orders_created'] = len(draft_order_items)
                self.log(f"Successfully created 2026 draft order for {len(draft_order_items)} players")
            else:
                self.log(f"DRY RUN: Would create 2026 draft order for {len(draft_order_items)} players")
            
            return True
            
        except Exception as e:
            self.log(f"Error creating 2026 draft order: {str(e)}", "ERROR")
            self.stats['errors'].append(f"Draft order creation: {str(e)}")
            return False

    def is_celebrity_active_for_2026(self, person_id: str) -> tuple[bool, str]:
        """Check if celebrity should be migrated to 2026 (didn't die in 2025)"""
        person = self.get_person(person_id)
        if not person:
            return False, "Person not found"
        
        death_date = person.get('death_date')
        if not death_date:
            return True, "Still alive"
        
        # Check if death was in 2025
        if death_date.startswith('2025'):
            return False, f"Died in 2025 ({death_date})"
        
        return True, f"Died in different year ({death_date})"

    def migrate_player_picks(self, player_id: str, player_name: str) -> bool:
        """Migrate ACTIVE 2025 picks for a player to 2026 (Active Picks Only strategy)"""
        self.log(f"Migrating picks for {player_name} ({player_id})...")
        
        try:
            # Get all 2025 picks for this player
            picks_2025 = self.get_player_picks(player_id, 2025)
            
            if not picks_2025:
                self.log(f"  No 2025 picks found for {player_name}")
                return True
            
            # Filter for active picks only (celebrities still alive)
            active_picks = []
            deceased_picks = []
            
            for pick in picks_2025:
                is_active, reason = self.is_celebrity_active_for_2026(pick['person_id'])
                if is_active:
                    active_picks.append(pick)
                else:
                    deceased_picks.append({'pick': pick, 'reason': reason})
            
            self.log(f"  Active picks to migrate: {len(active_picks)}")
            self.log(f"  Deceased picks to skip: {len(deceased_picks)}")
            
            # Log deceased picks being skipped
            for deceased in deceased_picks:
                person = self.get_person(deceased['pick']['person_id'])
                person_name = person['name'] if person else deceased['pick']['person_id']
                self.log(f"    Skipping {person_name}: {deceased['reason']}")
            
            # Create 2026 picks for active celebrities only
            pick_items = []
            for pick in active_picks:
                item = {
                    'PK': f'PLAYER#{player_id}',
                    'SK': f'PICK#2026#{pick["person_id"]}',
                    'Year': 2026,
                    'PersonID': pick['person_id'],
                    'Timestamp': self.migration_timestamp
                }
                pick_items.append(item)
            
            # Create draft slots tracking item
            available_slots = 20 - len(active_picks)
            draft_slots_item = {
                'PK': f'PLAYER#{player_id}',
                'SK': 'DRAFT_SLOTS#2026',
                'Type': 'DraftSlots',
                'Year': 2026,
                'MaxPicks': 20,
                'CurrentPicks': len(active_picks),
                'AvailableSlots': available_slots,
                'LastUpdated': self.migration_timestamp
            }
            
            if not self.dry_run:
                # Batch write the pick items and draft slots
                with self.table.batch_writer() as batch:
                    for item in pick_items:
                        batch.put_item(Item=item)
                    batch.put_item(Item=draft_slots_item)
                
                self.stats['picks_migrated'] += len(pick_items)
                self.log(f"  Successfully migrated {len(active_picks)} active picks for {player_name}")
                self.log(f"  Available draft slots: {available_slots}")
            else:
                self.log(f"  DRY RUN: Would migrate {len(active_picks)} active picks for {player_name}")
                self.log(f"  DRY RUN: Would create draft slots record (available: {available_slots})")
            
            return True
            
        except Exception as e:
            self.log(f"Error migrating picks for {player_name}: {str(e)}", "ERROR")
            self.stats['errors'].append(f"Player {player_name}: {str(e)}")
            return False

    def validate_migration(self) -> bool:
        """Validate that migration was successful"""
        self.log("Validating migration...")
        
        try:
            players = self.get_all_players()
            validation_errors = []
            
            for player in players:
                player_id = player['id']
                player_name = player['name']
                
                picks_2025 = self.get_player_picks(player_id, 2025)
                picks_2026 = self.get_player_picks(player_id, 2026)
                
                if len(picks_2025) != len(picks_2026):
                    error = f"{player_name}: 2025 picks ({len(picks_2025)}) != 2026 picks ({len(picks_2026)})"
                    validation_errors.append(error)
                    self.log(f"  VALIDATION ERROR: {error}", "ERROR")
                else:
                    self.log(f"  ✓ {player_name}: {len(picks_2026)} picks migrated correctly")
            
            if validation_errors:
                self.log(f"Validation failed with {len(validation_errors)} errors", "ERROR")
                return False
            else:
                self.log("✓ Migration validation successful")
                return True
                
        except Exception as e:
            self.log(f"Error during validation: {str(e)}", "ERROR")
            return False

    def run_migration(self) -> bool:
        """Execute the complete migration process"""
        self.log("Starting Deadpool 2025 to 2026 migration...")
        
        if self.dry_run:
            self.log("*** DRY RUN MODE - No changes will be made ***")
        
        try:
            # Step 1: Get 2025 leaderboard for draft order
            leaderboard = self.get_2025_leaderboard()
            
            # Step 2: Create 2026 draft order
            if not self.create_2026_draft_order(leaderboard):
                return False
            
            # Step 3: Migrate picks for each player
            players = self.get_all_players()
            for player in players:
                if not self.migrate_player_picks(player['id'], player['name']):
                    self.log(f"Failed to migrate picks for {player['name']}", "ERROR")
                    # Continue with other players
                else:
                    self.stats['players_processed'] += 1
            
            # Step 4: Validate migration (only if not dry run)
            if not self.dry_run:
                if not self.validate_migration():
                    return False
            
            # Print final statistics
            self.print_migration_summary()
            
            return len(self.stats['errors']) == 0
            
        except Exception as e:
            self.log(f"Migration failed: {str(e)}", "ERROR")
            return False

    def print_migration_summary(self):
        """Print migration statistics"""
        self.log("=" * 50)
        self.log("MIGRATION SUMMARY")
        self.log("=" * 50)
        self.log(f"Players processed: {self.stats['players_processed']}")
        self.log(f"Picks migrated: {self.stats['picks_migrated']}")
        self.log(f"Draft orders created: {self.stats['draft_orders_created']}")
        self.log(f"Errors: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            self.log("\nERRORS:")
            for error in self.stats['errors']:
                self.log(f"  - {error}")
        
        if self.dry_run:
            self.log("\n*** This was a DRY RUN - no changes were made ***")
        else:
            self.log(f"\n✓ Migration completed {'successfully' if len(self.stats['errors']) == 0 else 'with errors'}")


def main():
    parser = argparse.ArgumentParser(description='Migrate Deadpool game from 2025 to 2026')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool',
                       help='DynamoDB table name (default: Deadpool)')
    
    args = parser.parse_args()
    
    # Create migration instance
    migration = DeadpoolMigration(
        table_name=args.table_name,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    # Run migration
    success = migration.run_migration()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
