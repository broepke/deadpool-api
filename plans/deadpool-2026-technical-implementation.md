# Deadpool 2026 Technical Implementation Guide

## Overview

This document provides the complete technical implementation for migrating the Deadpool game from 2025 to 2026, including detailed migration scripts, validation procedures, and testing strategies.

## Quick Start Guide

### Prerequisites
- AWS CLI configured with appropriate DynamoDB permissions
- Python 3.9+ with boto3 installed
- Access to the Deadpool DynamoDB table

### Migration Steps
1. **Backup**: Create a backup of the current DynamoDB table
2. **Dry Run**: Execute migration script in dry-run mode
3. **Migration**: Run the actual migration
4. **Validation**: Verify migration success
5. **Testing**: Test all API endpoints with 2026 data

### Commands
```bash
# Step 1: Dry run to preview changes
python utilities/migrate_2025_to_2026.py --dry-run --verbose

# Step 2: Execute migration
python utilities/migrate_2025_to_2026.py --verbose

# Step 3: Validate migration
python utilities/validate_2026_migration.py --verbose
```

## Migration Scripts

### Primary Migration Script: `utilities/migrate_2025_to_2026.py`

```python
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

    def migrate_player_picks(self, player_id: str, player_name: str) -> bool:
        """Migrate all 2025 picks for a player to 2026"""
        self.log(f"Migrating picks for {player_name} ({player_id})...")
        
        try:
            # Get all 2025 picks for this player
            picks_2025 = self.get_player_picks(player_id, 2025)
            
            if not picks_2025:
                self.log(f"  No 2025 picks found for {player_name}")
                return True
            
            # Create 2026 picks
            pick_items = []
            for pick in picks_2025:
                item = {
                    'PK': f'PLAYER#{player_id}',
                    'SK': f'PICK#2026#{pick["person_id"]}',
                    'Year': 2026,
                    'PersonID': pick['person_id'],
                    'Timestamp': self.migration_timestamp
                }
                pick_items.append(item)
            
            if not self.dry_run:
                # Batch write the pick items
                with self.table.batch_writer() as batch:
                    for item in pick_items:
                        batch.put_item(Item=item)
                
                self.stats['picks_migrated'] += len(pick_items)
                self.log(f"  Successfully migrated {len(pick_items)} picks for {player_name}")
            else:
                self.log(f"  DRY RUN: Would migrate {len(pick_items)} picks for {player_name}")
            
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
```

### Validation Script: `utilities/validate_2026_migration.py`

```python
#!/usr/bin/env python3
"""
Deadpool 2026 Migration Validation Script

This script validates that the 2025 to 2026 migration was successful by checking:
- All players have identical pick counts between 2025 and 2026
- 2026 leaderboard starts at zero for all players
- Draft order is properly established for 2026
- No data corruption or missing records

Usage:
    python utilities/validate_2026_migration.py [--verbose]
"""

import boto3
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any
from botocore.exceptions import ClientError


class MigrationValidator:
    def __init__(self, table_name: str = "Deadpool", verbose: bool = False):
        self.table_name = table_name
        self.verbose = verbose
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
        self.validation_results = {
            'pick_count_matches': 0,
            'pick_count_mismatches': 0,
            'players_with_zero_2026_score': 0,
            'players_with_nonzero_2026_score': 0,
            'draft_order_positions': 0,
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
                    'name': f"{item.get('FirstName', '')} {item.get('LastName', '')}".strip()
                })
            
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

    def calculate_player_2026_score(self, player_id: str) -> int:
        """Calculate a player's 2026 score"""
        picks = self.get_player_picks(player_id, 2026)
        total_score = 0
        
        for pick in picks:
            person = self.get_person(pick['person_id'])
            if person and person.get('death_date'):
                # Check if death was in 2026
                death_year = int(person['death_date'][:4])
                if death_year == 2026:
                    age = person.get('age', 0)
                    score = 50 + (100 - age)
                    total_score += score
        
        return total_score

    def get_2026_draft_order(self) -> List[Dict[str, Any]]:
        """Get 2026 draft order"""
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={
                    ':pk': 'YEAR#2026'
                }
            )
            
            draft_order = []
            for item in response['Items']:
                # Extract draft order and player ID from SK
                sk_parts = item['SK'].split('#')
                if len(sk_parts) >= 3 and sk_parts[0] == 'ORDER':
                    draft_position = int(sk_parts[1])
                    player_id = sk_parts[2].replace('PLAYER', '')
                    
                    draft_order.append({
                        'position': draft_position,
                        'player_id': player_id
                    })
            
            # Sort by position
            draft_order.sort(key=lambda x: x['position'])
            return draft_order
            
        except Exception as e:
            self.log(f"Error getting 2026 draft order: {str(e)}", "ERROR")
            return []

    def validate_pick_counts(self) -> bool:
        """Validate that pick counts match between 2025 and 2026"""
        self.log("Validating pick counts...")
        
        players = self.get_all_players()
        all_valid = True
        
        for player in players:
            player_id = player['id']
            player_name = player['name']
            
            picks_2025 = self.get_player_picks(player_id, 2025)
            picks_2026 = self.get_player_picks(player_id, 2026)
            
            if len(picks_2025) == len(picks_2026):
                self.validation_results['pick_count_matches'] += 1
                self.log(f"  ✓ {player_name}: {len(picks_2026)} picks (matches 2025)")
            else:
                self.validation_results['pick_count_mismatches'] += 1
                error = f"{player_name}: 2025 picks ({len(picks_2025)}) != 2026 picks ({len(picks_2026)})"
                self.validation_results['errors'].append(error)
                self.log(f"  ✗ {error}", "ERROR")
                all_valid = False
        
        return all_valid

    def validate_2026_scores(self) -> bool:
        """Validate that all 2026 scores start at zero"""
        self.log("Validating 2026 scores...")
        
        players = self.get_all_players()
        all_valid = True
        
        for player in players:
            player_id = player['id']
            player_name = player['name']
            
            score_2026 = self.calculate_player_2026_score(player_id)
            
            if score_2026 == 0:
                self.validation_results['players_with_zero_2026_score'] += 1
                self.log(f"  ✓ {player_name}: 2026 score = 0 (correct)")
            else:
                self.validation_results['players_with_nonzero_2026_score'] += 1
                error = f"{player_name}: 2026 score = {score_2026} (should be 0)"
                self.validation_results['errors'].append(error)
                self.log(f"  ✗ {error}", "ERROR")
                all_valid = False
        
        return all_valid

    def validate_draft_order(self) -> bool:
        """Validate that 2026 draft order is properly established"""
        self.log("Validating 2026 draft order...")
        
        draft_order = self.get_2026_draft_order()
        players = self.get_all_players()
        
        if len(draft_order) != len(players):
            error = f"Draft order count ({len(draft_order)}) != player count ({len(players)})"
            self.validation_results['errors'].append(error)
            self.log(f"  ✗ {error}", "ERROR")
            return False
        
        # Check that positions are sequential
        expected_positions = list(range(1, len(players) + 1))
        actual_positions = [entry['position'] for entry in draft_order]
        
        if actual_positions != expected_positions:
            error = f"Draft positions not sequential: {actual_positions}"
            self.validation_results['errors'].append(error)
            self.log(f"  ✗ {error}", "ERROR")
            return False
        
        # Check that all players are included
        draft_player_ids = set(entry['player_id'] for entry in draft_order)
        all_player_ids = set(player['id'] for player in players)
        
        if draft_player_ids != all_player_ids:
            missing = all_player_ids - draft_player_ids
            extra = draft_player_ids - all_player_ids
            
            if missing:
                error = f"Players missing from draft order: {missing}"
                self.validation_results['errors'].append(error)
                self.log(f"  ✗ {error}", "ERROR")
            
            if extra:
                error = f"Extra players in draft order: {extra}"
                self.validation_results['errors'].append(error)
                self.log(f"  ✗ {error}", "ERROR")
            
            return False
        
        self.validation_results['draft_order_positions'] = len(draft_order)
        self.log(f"  ✓ 2026 draft order validated: {len(draft_order)} positions")
        
        for entry in draft_order:
            player = next((p for p in players if p['id'] == entry['player_id']), None)
            player_name = player['name'] if player else 'Unknown'
            self.log(f"    Position {entry['position']}: {player_name}")
        
        return True

    def run_validation(self) -> bool:
        """Execute complete validation"""
        self.log("Starting 2026 migration validation...")
        
        try:
            # Validate pick counts
            pick_counts_valid = self.validate_pick_counts()
            
            # Validate 2026 scores
            scores_valid = self.validate_2026_scores()
            
            # Validate draft order
            draft_order_valid = self.validate_draft_order()
            
            # Print summary
            self.print_validation_summary()
            
            return pick_counts_valid and scores_valid and draft_order_valid
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "ERROR")
            return False

    def print_validation_summary(self):
        """Print validation results summary"""
        self.log("=" * 50)
        self.log("VALIDATION SUMMARY")
        self.log("=" * 50)
        self.log(f"Pick count matches: {self.validation_results['pick_count_matches']}")
        self.log(f"Pick count mismatches: {self.validation_results['pick_count_mismatches']}")
        self.log(f"Players with zero 2026 score: {self.validation_results['players_with_zero_2026_score']}")
        self.log(f"Players with non-zero 2026 score: {self.validation_results['players_with_nonzero_2026_score']}")
        self.log(f"Draft order positions: {self.validation_results['draft_order_positions']}")
        self.log(f"Total errors: {len(self.validation_results['errors'])}")
        
        if self.validation_results['errors']:
            self.log("\nERRORS:")
            for error in self.validation_results['errors']:
                self.log(f"  - {error}")
        
        if len(self.validation_results['errors']) == 0:
            self.log("\n✓ All validations passed - migration successful!")
        else:
            self.log(f"\n✗ Validation failed with {len(self.validation_results['errors'])} errors")


def main():
    parser = argparse.ArgumentParser(description='Validate Deadpool 2026 migration')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool',
                       help='DynamoDB table name (default: Deadpool)')
    
    args = parser.parse_args()
    
    # Create validator instance
    validator = MigrationValidator(
        table_name=args.table_name,
        verbose=args.verbose
    )
    
    # Run validation
    success = validator.run_validation()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

## Database Schema Updates

### New Records Created

#### 2026 Draft Order Records
```
PK: YEAR#2026
SK: ORDER#01#PLAYER#{player_id}
Type: DraftOrder
Year: 2026
DraftOrder: 1
PlayerID: {player_id}
```

#### 2026 Player Pick Records
```
PK: PLAYER#{player_id}
SK: PICK#2026#{person_id}
Year: 2026
PersonID: {person_id}
Timestamp: 2026-01-01T00:00:00.000Z
```

## Application Code Updates

### Required Changes

1. **Default Year Logic**: Update application to default to 2026 for current year operations
2. **Cache Invalidation**: Clear all year-specific cached data
3. **API Endpoint Testing**: Ensure all endpoints work correctly with year=2026 parameter

### Files to Update

- [`src/services/picks.py`](src/services/picks.py): Update default year logic
- [`src/routers/deadpool.py`](src/routers/deadpool.py): Verify year parameter handling
- [`src/utils/caching.py`](src/utils/caching.py): Add cache invalidation for 2026

## Testing Strategy

### Pre-Migration Testing

1. **Dry Run Execution**
   ```bash
   python utilities/migrate_2025_to_2026.py --dry-run --verbose
   ```

2. **Development Environment Testing**
   - Run migration on development/staging environment
   - Validate all functionality works correctly
   - Test API endpoints with 2026 data

### Post-Migration Testing

1. **Data Validation**
   ```bash