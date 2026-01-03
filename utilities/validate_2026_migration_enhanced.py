#!/usr/bin/env python3
"""
Enhanced Deadpool 2026 Migration Validation Script

This script provides comprehensive validation of the 2025 to 2026 migration,
specifically designed for the "Active Picks Only" strategy. It validates:
- All active picks were migrated correctly
- No deceased celebrities were migrated
- Draft slots are calculated correctly
- Data integrity is maintained
- Business rules are enforced

Usage:
    python utilities/validate_2026_migration_enhanced.py [--verbose] [--fix-issues]
"""

import boto3
import argparse
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from botocore.exceptions import ClientError
from collections import defaultdict


class ValidationResult:
    """Container for validation results"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = True
        self.errors = []
        self.warnings = []
        self.info = []
    
    def add_error(self, message: str):
        self.errors.append(message)
        self.passed = False
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    def add_info(self, message: str):
        self.info.append(message)
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            'test_name': self.test_name,
            'passed': self.passed,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }


class EnhancedMigrationValidator:
    def __init__(self, table_name: str = "Deadpool", verbose: bool = False, fix_issues: bool = False):
        self.table_name = table_name
        self.verbose = verbose
        self.fix_issues = fix_issues
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
        self.validation_results = []
        self.overall_stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'total_errors': 0,
            'total_warnings': 0
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
                    'name': f"{item.get('FirstName', '')} {item.get('LastName', '')}".strip(),
                    'first_name': item.get('FirstName', ''),
                    'last_name': item.get('LastName', '')
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

    def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
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
                    'age': item.get('Age', 0),
                    'birth_date': item.get('BirthDate', '')
                }
            return None
            
        except Exception as e:
            self.log(f"Error getting person {person_id}: {str(e)}", "ERROR")
            return None

    def get_draft_slots(self, player_id: str, year: int = 2026) -> Optional[Dict[str, Any]]:
        """Get draft slots information for a player"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'PLAYER#{player_id}',
                    'SK': f'DRAFT_SLOTS#{year}'
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'max_picks': item.get('MaxPicks', 20),
                    'current_picks': item.get('CurrentPicks', 0),
                    'available_slots': item.get('AvailableSlots', 0),
                    'last_updated': item.get('LastUpdated', '')
                }
            return None
            
        except Exception as e:
            self.log(f"Error getting draft slots for player {player_id}: {str(e)}", "ERROR")
            return None

    def get_migration_metadata(self) -> Optional[Dict[str, Any]]:
        """Get migration metadata"""
        try:
            response = self.table.get_item(
                Key={
                    'PK': 'MIGRATION#2025_TO_2026',
                    'SK': 'METADATA'
                }
            )
            
            if 'Item' in response:
                return response['Item']
            return None
            
        except Exception as e:
            self.log(f"Error getting migration metadata: {str(e)}", "ERROR")
            return None

    def is_celebrity_died_in_2025(self, person_id: str) -> Tuple[bool, Optional[str]]:
        """Check if celebrity died in 2025"""
        person = self.get_person(person_id)
        if not person:
            return False, "Person not found"
        
        death_date = person.get('death_date')
        if not death_date:
            return False, "Still alive"
        
        if death_date.startswith('2025'):
            return True, death_date
        
        return False, f"Died in different year ({death_date})"

    def validate_migration_metadata(self) -> ValidationResult:
        """Validate migration metadata exists and is correct"""
        result = ValidationResult("Migration Metadata")
        
        try:
            metadata = self.get_migration_metadata()
            
            if not metadata:
                result.add_error("Migration metadata record not found")
                return result
            
            # Check required fields
            required_fields = ['MigrationDate', 'Strategy', 'PlayersProcessed', 'Status']
            for field in required_fields:
                if field not in metadata:
                    result.add_error(f"Missing required field: {field}")
            
            # Validate strategy
            if metadata.get('Strategy') != 'ACTIVE_PICKS_ONLY':
                result.add_error(f"Expected strategy 'ACTIVE_PICKS_ONLY', got '{metadata.get('Strategy')}'")
            
            # Validate status
            status = metadata.get('Status', '')
            if status not in ['COMPLETED', 'COMPLETED_WITH_ERRORS']:
                result.add_error(f"Invalid migration status: {status}")
            
            result.add_info(f"Migration completed on: {metadata.get('MigrationDate')}")
            result.add_info(f"Players processed: {metadata.get('PlayersProcessed')}")
            result.add_info(f"Active picks migrated: {metadata.get('ActivePicksMigrated')}")
            result.add_info(f"Deceased picks skipped: {metadata.get('DeceasedPicksSkipped')}")
            
        except Exception as e:
            result.add_error(f"Error validating migration metadata: {str(e)}")
        
        return result

    def validate_pick_counts(self) -> ValidationResult:
        """Validate that pick counts are correct for all players"""
        result = ValidationResult("Pick Count Validation")
        
        try:
            players = self.get_all_players()
            
            for player in players:
                player_id = player['id']
                player_name = player['name']
                
                # Get picks for both years
                picks_2025 = self.get_player_picks(player_id, 2025)
                picks_2026 = self.get_player_picks(player_id, 2026)
                
                # Calculate expected 2026 picks (active picks from 2025)
                active_picks_2025 = []
                deceased_picks_2025 = []
                
                for pick in picks_2025:
                    died_in_2025, death_info = self.is_celebrity_died_in_2025(pick['person_id'])
                    if died_in_2025:
                        deceased_picks_2025.append(pick)
                    else:
                        active_picks_2025.append(pick)
                
                expected_2026_count = len(active_picks_2025)
                actual_2026_count = len(picks_2026)
                
                if actual_2026_count != expected_2026_count:
                    result.add_error(
                        f"{player_name}: Expected {expected_2026_count} picks in 2026, "
                        f"got {actual_2026_count} (had {len(picks_2025)} in 2025, "
                        f"{len(deceased_picks_2025)} died in 2025)"
                    )
                else:
                    result.add_info(
                        f"✓ {player_name}: {actual_2026_count} picks migrated correctly "
                        f"({len(deceased_picks_2025)} deceased picks skipped)"
                    )
                
                # Validate that all 2026 picks are from active 2025 picks
                active_person_ids = {pick['person_id'] for pick in active_picks_2025}
                migrated_person_ids = {pick['person_id'] for pick in picks_2026}
                
                if migrated_person_ids != active_person_ids:
                    missing = active_person_ids - migrated_person_ids
                    extra = migrated_person_ids - active_person_ids
                    
                    if missing:
                        result.add_error(f"{player_name}: Missing migrated picks: {missing}")
                    if extra:
                        result.add_error(f"{player_name}: Extra migrated picks: {extra}")
                
        except Exception as e:
            result.add_error(f"Error validating pick counts: {str(e)}")
        
        return result

    def validate_no_deceased_migrated(self) -> ValidationResult:
        """Validate that no celebrities who died in 2025 were migrated to 2026"""
        result = ValidationResult("Deceased Celebrity Check")
        
        try:
            players = self.get_all_players()
            deceased_migrated = []
            
            for player in players:
                picks_2026 = self.get_player_picks(player['id'], 2026)
                
                for pick in picks_2026:
                    died_in_2025, death_info = self.is_celebrity_died_in_2025(pick['person_id'])
                    if died_in_2025:
                        person = self.get_person(pick['person_id'])
                        person_name = person['name'] if person else pick['person_id']
                        deceased_migrated.append({
                            'player': player['name'],
                            'celebrity': person_name,
                            'person_id': pick['person_id'],
                            'death_date': death_info
                        })
            
            if deceased_migrated:
                result.add_error(f"Found {len(deceased_migrated)} deceased celebrities migrated to 2026:")
                for item in deceased_migrated:
                    result.add_error(
                        f"  {item['player']} -> {item['celebrity']} (died {item['death_date']})"
                    )
            else:
                result.add_info("✓ No deceased celebrities were migrated to 2026")
                
        except Exception as e:
            result.add_error(f"Error checking deceased celebrities: {str(e)}")
        
        return result

    def validate_draft_slots(self) -> ValidationResult:
        """Validate draft slots are calculated correctly"""
        result = ValidationResult("Draft Slots Validation")
        
        try:
            players = self.get_all_players()
            
            for player in players:
                player_id = player['id']
                player_name = player['name']
                
                # Get draft slots record
                draft_slots = self.get_draft_slots(player_id)
                picks_2026 = self.get_player_picks(player_id, 2026)
                
                if not draft_slots:
                    result.add_error(f"{player_name}: No draft slots record found")
                    continue
                
                # Validate calculations
                expected_current_picks = len(picks_2026)
                expected_available_slots = 20 - expected_current_picks
                
                if draft_slots['current_picks'] != expected_current_picks:
                    result.add_error(
                        f"{player_name}: Draft slots current_picks ({draft_slots['current_picks']}) "
                        f"doesn't match actual picks ({expected_current_picks})"
                    )
                
                if draft_slots['available_slots'] != expected_available_slots:
                    result.add_error(
                        f"{player_name}: Draft slots available_slots ({draft_slots['available_slots']}) "
                        f"doesn't match calculated slots ({expected_available_slots})"
                    )
                
                if draft_slots['max_picks'] != 20:
                    result.add_error(f"{player_name}: Max picks should be 20, got {draft_slots['max_picks']}")
                
                if draft_slots['current_picks'] + draft_slots['available_slots'] != 20:
                    result.add_error(
                        f"{player_name}: Current picks + available slots != 20 "
                        f"({draft_slots['current_picks']} + {draft_slots['available_slots']})"
                    )
                
                result.add_info(
                    f"✓ {player_name}: {draft_slots['current_picks']} picks, "
                    f"{draft_slots['available_slots']} slots available"
                )
                
        except Exception as e:
            result.add_error(f"Error validating draft slots: {str(e)}")
        
        return result

    def validate_2026_leaderboard_reset(self) -> ValidationResult:
        """Validate that 2026 leaderboard shows zero points for all players"""
        result = ValidationResult("2026 Leaderboard Reset")
        
        try:
            players = self.get_all_players()
            
            for player in players:
                player_id = player['id']
                player_name = player['name']
                picks_2026 = self.get_player_picks(player_id, 2026)
                
                # Calculate 2026 score (should be zero since no one died in 2026 yet)
                total_score = 0
                for pick in picks_2026:
                    person = self.get_person(pick['person_id'])
                    if person and person.get('death_date'):
                        death_year = int(person['death_date'][:4])
                        if death_year == 2026:
                            age = person.get('age', 0)
                            score = 50 + (100 - age)
                            total_score += score
                
                if total_score != 0:
                    result.add_warning(
                        f"{player_name}: Has {total_score} points in 2026 "
                        f"(someone may have died in 2026 already)"
                    )
                else:
                    result.add_info(f"✓ {player_name}: 0 points in 2026 (as expected)")
                
        except Exception as e:
            result.add_error(f"Error validating 2026 leaderboard: {str(e)}")
        
        return result

    def validate_draft_order_2026(self) -> ValidationResult:
        """Validate 2026 draft order exists and is reasonable"""
        result = ValidationResult("2026 Draft Order")
        
        try:
            # Get 2026 draft order
            response = self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ':pk': 'YEAR#2026',
                    ':sk_prefix': 'ORDER#'
                }
            )
            
            draft_orders = []
            for item in response['Items']:
                draft_orders.append({
                    'position': item.get('DraftOrder'),
                    'player_id': item.get('PlayerID'),
                    'sk': item['SK']
                })
            
            # Sort by position
            draft_orders.sort(key=lambda x: x['position'])
            
            players = self.get_all_players()
            expected_count = len(players)
            
            if len(draft_orders) != expected_count:
                result.add_error(
                    f"Expected {expected_count} draft order entries, got {len(draft_orders)}"
                )
            
            # Validate positions are sequential
            for i, order in enumerate(draft_orders, 1):
                if order['position'] != i:
                    result.add_error(f"Draft position {i} missing or incorrect")
            
            # Validate all players have draft positions
            draft_player_ids = {order['player_id'] for order in draft_orders}
            all_player_ids = {player['id'] for player in players}
            
            missing_players = all_player_ids - draft_player_ids
            extra_players = draft_player_ids - all_player_ids
            
            if missing_players:
                result.add_error(f"Players missing from draft order: {missing_players}")
            if extra_players:
                result.add_error(f"Unknown players in draft order: {extra_players}")
            
            result.add_info(f"✓ 2026 draft order created with {len(draft_orders)} positions")
            
        except Exception as e:
            result.add_error(f"Error validating draft order: {str(e)}")
        
        return result

    def validate_data_integrity(self) -> ValidationResult:
        """Validate overall data integrity"""
        result = ValidationResult("Data Integrity")
        
        try:
            players = self.get_all_players()
            
            # Check for orphaned picks
            all_person_ids = set()
            for player in players:
                picks_2026 = self.get_player_picks(player['id'], 2026)
                for pick in picks_2026:
                    all_person_ids.add(pick['person_id'])
            
            # Verify all person IDs exist
            missing_persons = []
            for person_id in all_person_ids:
                person = self.get_person(person_id)
                if not person:
                    missing_persons.append(person_id)
            
            if missing_persons:
                result.add_error(f"Missing person records: {missing_persons}")
            else:
                result.add_info(f"✓ All {len(all_person_ids)} referenced celebrities exist")
            
            # Check for duplicate picks within 2026
            for player in players:
                picks_2026 = self.get_player_picks(player['id'], 2026)
                person_ids = [pick['person_id'] for pick in picks_2026]
                
                if len(person_ids) != len(set(person_ids)):
                    duplicates = [pid for pid in set(person_ids) if person_ids.count(pid) > 1]
                    result.add_error(f"{player['name']}: Duplicate picks in 2026: {duplicates}")
            
            result.add_info("✓ No duplicate picks found within players")
            
        except Exception as e:
            result.add_error(f"Error validating data integrity: {str(e)}")
        
        return result

    def run_all_validations(self) -> bool:
        """Run all validation tests"""
        self.log("Starting Enhanced Migration Validation...")
        
        # Define all validation tests
        validation_tests = [
            self.validate_migration_metadata,
            self.validate_pick_counts,
            self.validate_no_deceased_migrated,
            self.validate_draft_slots,
            self.validate_2026_leaderboard_reset,
            self.validate_draft_order_2026,
            self.validate_data_integrity
        ]
        
        # Run all tests
        for test_func in validation_tests:
            try:
                result = test_func()
                self.validation_results.append(result)
                
                self.overall_stats['total_tests'] += 1
                if result.passed:
                    self.overall_stats['passed_tests'] += 1
                else:
                    self.overall_stats['failed_tests'] += 1
                
                self.overall_stats['total_errors'] += len(result.errors)
                self.overall_stats['total_warnings'] += len(result.warnings)
                
                # Log test results
                status = "PASS" if result.passed else "FAIL"
                self.log(f"{status}: {result.test_name}")
                
                if result.errors and self.verbose:
                    for error in result.errors:
                        self.log(f"  ERROR: {error}", "ERROR")
                
                if result.warnings and self.verbose:
                    for warning in result.warnings:
                        self.log(f"  WARNING: {warning}", "WARN")
                
            except Exception as e:
                self.log(f"FAIL: {test_func.__name__} - {str(e)}", "ERROR")
                self.overall_stats['total_tests'] += 1
                self.overall_stats['failed_tests'] += 1
                self.overall_stats['total_errors'] += 1
        
        # Print summary
        self.print_validation_summary()
        
        return self.overall_stats['failed_tests'] == 0

    def print_validation_summary(self):
        """Print comprehensive validation summary"""
        self.log("=" * 60)
        self.log("VALIDATION SUMMARY")
        self.log("=" * 60)
        
        stats = self.overall_stats
        self.log(f"Total tests: {stats['total_tests']}")
        self.log(f"Passed: {stats['passed_tests']}")
        self.log(f"Failed: {stats['failed_tests']}")
        self.log(f"Total errors: {stats['total_errors']}")
        self.log(f"Total warnings: {stats['total_warnings']}")
        
        # Print detailed results
        for result in self.validation_results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            self.log(f"\n{status}: {result.test_name}")
            
            if result.errors:
                self.log("  Errors:")
                for error in result.errors:
                    self.log(f"    - {error}")
            
            if result.warnings:
                self.log("  Warnings:")
                for warning in result.warnings:
                    self.log(f"    - {warning}")
            
            if result.info and self.verbose:
                self.log("  Info:")
                for info in result.info:
                    self.log(f"    - {info}")
        
        # Overall result
        if stats['failed_tests'] == 0:
            self.log(f"\n🎉 ALL VALIDATIONS PASSED!")
            self.log("Migration appears to be successful.")
        else:
            self.log(f"\n❌ {stats['failed_tests']} VALIDATION(S) FAILED")
            self.log("Migration may have issues that need attention.")

    def export_validation_report(self, filename: str = None):
        """Export detailed validation report to JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"migration_validation_report_{timestamp}.json"
        
        report = {
            'validation_timestamp': datetime.now().isoformat(),
            'overall_stats': self.overall_stats,
            'test_results': [result.get_summary() for result in self.validation_results]
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log(f"Validation report exported to: {filename}")


def main():
    parser = argparse.ArgumentParser(description='Enhanced Deadpool 2026 Migration Validation')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed validation information')
    parser.add_argument('--table-name', default='Deadpool',
                       help='DynamoDB table name (default: Deadpool)')
    parser.add_argument('--export-report', action='store_true',
                       help='Export detailed validation report to JSON')
    parser.add_argument('--fix-issues', action='store_true',
                       help='Attempt to fix minor issues automatically')
    
    args = parser.parse_args()
    
    # Create validator instance
    validator = EnhancedMigrationValidator(
        table_name=args.table_name,
        verbose=args.verbose,
        fix_issues=args.fix_issues
    )
    
    # Run validation
    success = validator.run_all_validations()
    
    # Export report if requested
    if args.export_report:
        validator.export_validation_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()