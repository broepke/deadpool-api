import csv
import os

def remove_inactive_players(input_file: str, output_dir: str, inactive_players: list):
    """
    Remove picks from inactive players and move them to a separate file.
    
    Args:
        input_file: Path to the input CSV file (active_picks.csv)
        output_dir: Directory to store output files
        inactive_players: List of player IDs to remove
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup temporary file for active picks and file for inactive picks
    temp_file = os.path.join(output_dir, 'temp_active_picks.csv')
    inactive_file = os.path.join(output_dir, 'inactive_player_picks.csv')
    
    # Track counts
    active_count = 0
    inactive_count = 0
    
    # Process the files
    with open(input_file, 'r') as infile, \
         open(temp_file, 'w', newline='') as active_out, \
         open(inactive_file, 'w', newline='') as inactive_out:
        
        # Setup CSV readers and writers
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        active_writer = csv.DictWriter(active_out, fieldnames=fieldnames)
        inactive_writer = csv.DictWriter(inactive_out, fieldnames=fieldnames)
        
        # Write headers
        active_writer.writeheader()
        inactive_writer.writeheader()
        
        # Process each row
        for row in reader:
            if row['PLAYER_ID'] in inactive_players:
                inactive_writer.writerow(row)
                inactive_count += 1
            else:
                active_writer.writerow(row)
                active_count += 1
    
    # Replace original active_picks.csv with the new version
    os.replace(temp_file, input_file)
    
    print(f"Processing complete:")
    print(f"Active picks remaining: {active_count}")
    print(f"Inactive picks removed: {inactive_count}")
    print(f"\nOutput files:")
    print(f"Updated active picks: {input_file}")
    print(f"Inactive picks: {inactive_file}")

if __name__ == "__main__":
    # List of inactive player IDs
    inactive_players = [
        "049864b8-1081-7020-7ec9-02f2c836277c",
        "2498f4b8-b061-70b9-1c42-84ceae3b40eb",
        "b4682458-6011-7019-f3e2-60c89d3ee00f"
    ]
    
    input_file = "data/cleaned/active_picks.csv"
    output_dir = "data/cleaned"
    
    remove_inactive_players(input_file, output_dir, inactive_players)