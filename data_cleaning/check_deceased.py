import csv
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.dynamodb import DynamoDBClient

async def check_deceased_picks(input_file: str, output_dir: str):
    """
    Check player picks against DynamoDB to separate deceased people's picks.
    
    Args:
        input_file: Path to the input CSV file
        output_dir: Directory to store output files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize DynamoDB client
    db_client = DynamoDBClient()
    
    # Prepare output files
    active_file = os.path.join(output_dir, 'active_picks.csv')
    deceased_file = os.path.join(output_dir, 'deceased_picks.csv')
    
    # Read input file and process records
    with open(input_file, 'r') as infile, \
         open(active_file, 'w', newline='') as active_out, \
         open(deceased_file, 'w', newline='') as deceased_out:
        
        # Set up CSV readers and writers
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        active_writer = csv.DictWriter(active_out, fieldnames=fieldnames)
        deceased_writer = csv.DictWriter(deceased_out, fieldnames=fieldnames)
        
        # Write headers
        active_writer.writeheader()
        deceased_writer.writeheader()
        
        # Process each row
        active_count = 0
        deceased_count = 0
        
        for row in reader:
            person_id = row['PEOPLE_ID']
            person = await db_client.get_person(person_id)
            
            if person and person.get('status') == 'deceased':
                deceased_writer.writerow(row)
                deceased_count += 1
            else:
                active_writer.writerow(row)
                active_count += 1
                
        print(f"Processing complete:")
        print(f"Active picks: {active_count}")
        print(f"Deceased picks: {deceased_count}")
        print(f"\nOutput files:")
        print(f"Active picks: {active_file}")
        print(f"Deceased picks: {deceased_file}")

if __name__ == "__main__":
    input_file = "data/player_picks_2025.csv"
    output_dir = "data/cleaned"
    
    # Run the async function
    asyncio.run(check_deceased_picks(input_file, output_dir))