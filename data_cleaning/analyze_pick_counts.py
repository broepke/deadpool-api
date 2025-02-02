import csv
from collections import defaultdict
import os

def analyze_pick_counts(input_file: str):
    """
    Analyze the number of picks per player and verify each has exactly 20 picks.
    
    Args:
        input_file: Path to the active_picks.csv file
    """
    # Dictionary to store pick counts per player
    pick_counts = defaultdict(int)
    # Dictionary to store actual picks for players with incorrect counts
    player_picks = defaultdict(list)
    
    # Read and process the file
    with open(input_file, 'r') as infile:
        reader = csv.DictReader(infile)
        
        for row in reader:
            player_id = row['PLAYER_ID']
            pick_counts[player_id] += 1
            player_picks[player_id].append(row)
    
    # Analyze results
    correct_count = 0
    incorrect_count = 0
    
    print("\nPick Count Analysis:")
    print("=" * 80)
    print(f"{'Player ID':<40} {'Pick Count':<10} {'Status':<10}")
    print("-" * 80)
    
    for player_id, count in sorted(pick_counts.items()):
        status = "OK" if count == 20 else "ERROR"
        if count == 20:
            correct_count += 1
        else:
            incorrect_count += 1
        print(f"{player_id:<40} {count:<10} {status:<10}")
    
    print("\nSummary:")
    print(f"Total players: {len(pick_counts)}")
    print(f"Players with exactly 20 picks: {correct_count}")
    print(f"Players with incorrect pick count: {incorrect_count}")
    
    # If there are any players with incorrect pick counts, create a detailed report
    if incorrect_count > 0:
        report_file = os.path.join(os.path.dirname(input_file), 'pick_count_errors.csv')
        with open(report_file, 'w', newline='') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(['Player ID', 'Pick Count', 'Expected Count', 'Difference'])
            
            for player_id, count in pick_counts.items():
                if count != 20:
                    writer.writerow([player_id, count, 20, count - 20])
        
        print(f"\nDetailed error report written to: {report_file}")

if __name__ == "__main__":
    input_file = "data/cleaned/active_picks.csv"
    analyze_pick_counts(input_file)