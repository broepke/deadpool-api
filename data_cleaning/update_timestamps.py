import csv
import os
from datetime import datetime

def update_timestamps(input_file: str):
    """
    Update all timestamps in the CSV to midnight on Feb 1, 2025.
    
    Args:
        input_file: Path to the active_picks.csv file
    """
    # Create a temporary file for the updates
    temp_file = os.path.join(os.path.dirname(input_file), 'temp_active_picks.csv')
    new_timestamp = "2025-02-01 00:00:00.000"
    rows_updated = 0
    
    # Process the file
    with open(input_file, 'r') as infile, \
         open(temp_file, 'w', newline='') as outfile:
        
        # Setup CSV reader and writer
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        
        # Write header
        writer.writeheader()
        
        # Process each row
        for row in reader:
            row['TIMESTAMP'] = new_timestamp
            writer.writerow(row)
            rows_updated += 1
    
    # Replace original file with updated version
    os.replace(temp_file, input_file)
    
    print(f"Processing complete:")
    print(f"Total rows updated: {rows_updated}")
    print(f"New timestamp: {new_timestamp}")
    print(f"Updated file: {input_file}")

if __name__ == "__main__":
    input_file = "data/cleaned/active_picks.csv"
    update_timestamps(input_file)