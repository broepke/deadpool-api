#!/usr/bin/env python3
"""
Script to clean up test people that were added to the database during testing.

This script:
1. Identifies all people with names starting with "Test Person"
2. Deletes their records from the database
3. Deletes any picks associated with them
"""
import os
import sys
import boto3
import argparse
from datetime import datetime
from typing import Dict, Any, List

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Clean up test people from the database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making any changes",
    )
    parser.add_argument(
        "--table-name",
        type=str,
        default="Deadpool",
        help="The name of the DynamoDB table",
    )
    return parser.parse_args()

def get_known_test_people(table) -> List[Dict[str, Any]]:
    """
    Get the known test people by their IDs.
    
    Args:
        table: DynamoDB table object
        
    Returns:
        List of test people
    """
    print("Getting known test people...")
    
    # IDs of the known test people
    test_person_ids = [
        "c0051ae0-0f2d-4dca-a72a-ce3685b03249",  # Test Person 1743623537
        "3d0be594-44df-4199-acd4-817588a2f0c8"   # Test Person Task-1
    ]
    
    test_people = []
    
    # Get each test person
    for person_id in test_person_ids:
        try:
            response = table.get_item(
                Key={"PK": f"PERSON#{person_id}", "SK": "DETAILS"}
            )
            
            item = response.get("Item")
            if item:
                test_people.append(item)
                print(f"Found test person: {item.get('name')} (ID: {person_id})")
        except Exception as e:
            print(f"Error getting test person {person_id}: {e}")
    
    print(f"Found {len(test_people)} test people")
    return test_people

def find_picks_for_people(table, person_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Find all picks associated with the given person IDs.
    
    Args:
        table: DynamoDB table object
        person_ids: List of person IDs
        
    Returns:
        List of picks
    """
    print("Finding picks for test people...")
    
    all_picks = []
    
    # Scan for all picks
    response = table.scan(
        FilterExpression="begins_with(SK, :pick_prefix)",
        ExpressionAttributeValues={
            ":pick_prefix": "PICK#"
        }
    )
    
    items = response.get("Items", [])
    
    # Handle pagination if there are more items
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="begins_with(SK, :pick_prefix)",
            ExpressionAttributeValues={
                ":pick_prefix": "PICK#"
            },
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))
    
    # Filter picks for the given person IDs
    for item in items:
        sk = item.get("SK", "")
        parts = sk.split("#")
        if len(parts) >= 3:
            person_id = "#".join(parts[2:])
            
            # Use PersonID attribute if available
            if "PersonID" in item:
                person_id = item["PersonID"]
            
            if person_id in person_ids:
                all_picks.append(item)
    
    print(f"Found {len(all_picks)} picks for test people")
    return all_picks

def delete_items(table, items: List[Dict[str, Any]], dry_run: bool = False):
    """
    Delete the given items from the database.
    
    Args:
        table: DynamoDB table object
        items: List of items to delete
        dry_run: If True, don't make any changes
    """
    for item in items:
        pk = item.get("PK")
        sk = item.get("SK")
        
        print(f"Deleting item: {pk} / {sk}")
        
        if not dry_run:
            try:
                table.delete_item(Key={"PK": pk, "SK": sk})
                print("  ✅ Deleted successfully")
            except Exception as e:
                print(f"  ❌ Error deleting item: {e}")
        else:
            print("  (Dry run, no changes made)")
        
        print()

def main():
    """Main function."""
    args = parse_args()
    
    print(f"Starting cleanup script at {datetime.now().isoformat()}")
    print(f"Table name: {args.table_name}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Initialize DynamoDB client
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(args.table_name)
    
    # Get known test people
    test_people = get_known_test_people(table)
    
    if test_people:
        # Extract person IDs
        person_ids = []
        for person in test_people:
            pk = person.get("PK", "")
            if pk.startswith("PERSON#"):
                person_id = pk[7:]  # Remove "PERSON#" prefix
                person_ids.append(person_id)
                print(f"Test person: {person.get('name')} (ID: {person_id})")
        
        print()
        
        # Find picks for test people
        picks = find_picks_for_people(table, person_ids)
        
        # Delete picks
        if picks:
            print("\nDeleting picks for test people...")
            delete_items(table, picks, args.dry_run)
        
        # Delete test people
        print("\nDeleting test people...")
        delete_items(table, test_people, args.dry_run)
        
        print(f"\nCleaned up {len(test_people)} test people and {len(picks)} picks")
    else:
        print("\nNo test people found")
    
    print(f"\nFinished at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()