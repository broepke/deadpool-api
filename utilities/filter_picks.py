#!/usr/bin/env python3
import csv

def filter_picks(input_file: str, kept_file: str, excluded_file: str):
    """
    Filter player picks into two files:
    - kept_file: rows where PLAYER_ID is not in excluded players
    - excluded_file: rows where PLAYER_ID is in excluded players
    """
    excluded_players = {
        "2498f4b8-b061-70b9-1c42-84ceae3b40eb",
        "049864b8-1081-7020-7ec9-02f2c836277c",
        "b4682458-6011-7019-f3e2-60c89d3ee00f"
    }
    
    # Read the input CSV and store rows
    kept_rows = []
    excluded_rows = []
    header = None
    
    print(f"Reading from {input_file}...")
    with open(input_file, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)  # Get header row
        kept_rows.append(header)
        excluded_rows.append(header)
        
        for row in reader:
            player_id = row[0]  # PLAYER_ID is the first column
            if player_id not in excluded_players:
                kept_rows.append(row)
            else:
                excluded_rows.append(row)
                
    # Write the kept rows
    print(f"Writing kept picks to {kept_file}...")
    with open(kept_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(kept_rows)
    
    # Write the excluded rows
    print(f"Writing excluded picks to {excluded_file}...")
    with open(excluded_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(excluded_rows)
    
    print(f"Excluded {len(excluded_rows) - 1} rows")
    print(f"Kept {len(kept_rows) - 1} rows")

if __name__ == '__main__':
    input_file = 'data/player_picks_2025.csv'
    kept_file = 'data/player_picks_2025_filtered.csv'
    excluded_file = 'data/player_picks_2025_excluded.csv'
    
    filter_picks(input_file, kept_file, excluded_file)