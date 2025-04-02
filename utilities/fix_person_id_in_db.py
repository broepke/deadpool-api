#!/usr/bin/env python3
"""
Script to fix person IDs stored as string representations of dictionaries in the database.

This script:
1. Scans the database for all picks
2. Checks if any person_id is stored as a string representation of a dictionary
3. Extracts the actual person_id from the dictionary
4. Updates the database record with the correct person_id
"""
import os
import sys
import boto3
import ast
import argparse
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fix person IDs in the database")
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

def extract_person_id(person_id_str: str) -> str:
    """
    Extract the actual person_id from a string representation of a dictionary.
    
    Args:
        person_id_str: String representation of a dictionary
        
    Returns:
        The extracted person_id or the original string if it's not a dictionary
    """
    try:
        if isinstance(person_id_str, str) and person_id_str.startswith("{") and "person_id" in person_id_str:
            person_dict = ast.literal_eval(person_id_str)
            if "person_id" in person_dict:
                return person_dict["person_id"]
    except Exception as e:
        print(f"Error parsing person_id from string: {e}")
    
    return person_id_str

def scan_for_picks(table) -> List[Dict[str, Any]]:
    """
    Scan the database for all picks.
    
    Args:
        table: DynamoDB table object
        
    Returns:
        List of picks
    """
    print("Scanning for picks...")
    
    # Use a FilterExpression to find all items with SK starting with "PICK#"
    response = table.scan(
        FilterExpression="begins_with(SK, :pick_prefix)",
        ExpressionAttributeValues={":pick_prefix": "PICK#"}
    )
    
    items = response.get("Items", [])
    
    # Handle pagination if there are more items
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="begins_with(SK, :pick_prefix)",
            ExpressionAttributeValues={":pick_prefix": "PICK#"},
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))
    
    print(f"Found {len(items)} picks")
    return items

def identify_problematic_picks(picks: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], str]]:
    """
    Identify picks with person IDs stored as string representations of dictionaries.
    
    Args:
        picks: List of picks
        
    Returns:
        List of tuples containing the pick and the extracted person_id
    """
    problematic_picks = []
    
    for pick in picks:
        # Extract the person_id from the SK
        sk = pick.get("SK", "")
        parts = sk.split("#")
        if len(parts) >= 3:
            person_id = "#".join(parts[2:])
            
            # Check if it's a string representation of a dictionary
            if isinstance(person_id, str) and person_id.startswith("{") and "person_id" in person_id:
                extracted_id = extract_person_id(person_id)
                if extracted_id != person_id:
                    problematic_picks.append((pick, extracted_id))
    
    print(f"Found {len(problematic_picks)} problematic picks")
    return problematic_picks

def fix_problematic_picks(table, problematic_picks: List[Tuple[Dict[str, Any], str]], dry_run: bool = False):
    """
    Fix picks with person IDs stored as string representations of dictionaries.
    
    Args:
        table: DynamoDB table object
        problematic_picks: List of tuples containing the pick and the extracted person_id
        dry_run: If True, don't make any changes
    """
    for pick, extracted_id in problematic_picks:
        pk = pick.get("PK")
        sk = pick.get("SK")
        
        # Extract the year from the SK
        parts = sk.split("#")
        if len(parts) >= 2:
            year = parts[1]
            
            # Create the new SK with the extracted person_id
            new_sk = f"PICK#{year}#{extracted_id}"
            
            print(f"Fixing pick: {pk} / {sk}")
            print(f"  Old person_id: {sk.split('#', 2)[2]}")
            print(f"  New person_id: {extracted_id}")
            print(f"  New SK: {new_sk}")
            
            if not dry_run:
                try:
                    # Create a new item with the correct SK
                    new_item = pick.copy()
                    new_item["SK"] = new_sk
                    new_item["PersonID"] = extracted_id
                    new_item["Year"] = int(year)
                    
                    # Put the new item
                    table.put_item(Item=new_item)
                    
                    # Delete the old item
                    table.delete_item(Key={"PK": pk, "SK": sk})
                    
                    print("  ✅ Fixed successfully")
                except Exception as e:
                    print(f"  ❌ Error fixing pick: {e}")
            else:
                print("  (Dry run, no changes made)")
            
            print()

def main():
    """Main function."""
    args = parse_args()
    
    print(f"Starting person ID fix script at {datetime.now().isoformat()}")
    print(f"Table name: {args.table_name}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Initialize DynamoDB client
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(args.table_name)
    
    # Scan for picks
    picks = scan_for_picks(table)
    
    # Identify problematic picks
    problematic_picks = identify_problematic_picks(picks)
    
    # Fix problematic picks
    if problematic_picks:
        print("\nFixing problematic picks...")
        fix_problematic_picks(table, problematic_picks, args.dry_run)
        
        print(f"\nFixed {len(problematic_picks)} problematic picks")
    else:
        print("\nNo problematic picks found")
    
    print(f"\nFinished at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()