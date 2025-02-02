import pandas as pd
import json
import os

def format_timestamp(timestamp):
    """Format timestamp to ISO 8601 by replacing space with 'T'."""
    if pd.isna(timestamp):
        return None
    return timestamp.replace(" ", "T")

def chunk_list(lst, chunk_size):
    """Split a list into smaller chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def generate_batch_write_json(data, table_name):
    """Format data for DynamoDB batch-write-item JSON structure."""
    put_requests = [{"PutRequest": {"Item": item}} for item in data]
    chunked_requests = chunk_list(put_requests, 25)
    return [{table_name: chunk} for chunk in chunked_requests]

def process_2025_picks(picks_csv, output_directory, table_name):
    """Process the 2025 picks CSV and generate JSON files for DynamoDB loading."""
    os.makedirs(output_directory, exist_ok=True)

    # Process Player Picks
    picks_df = pd.read_csv(picks_csv)
    player_picks = []

    for _, row in picks_df.iterrows():
        pk = f"PLAYER#{row['PLAYER_ID']}"
        sk = f"PICK#{row['YEAR']}#{row['PEOPLE_ID']}"
        attributes = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "Year": {"N": str(row["YEAR"])},
            "PersonID": {"S": row["PEOPLE_ID"]},
            "Timestamp": {"S": format_timestamp(row["TIMESTAMP"])},
        }
        player_picks.append(attributes)

    # Save as batch-write compatible JSON files
    batch_writes = generate_batch_write_json(player_picks, table_name)
    for i, batch in enumerate(batch_writes):
        output_path = os.path.join(output_directory, f"Picks2025_batch_{i+1}.json")
        with open(output_path, "w") as f:
            json.dump(batch, f, indent=2)
        print(f"Saved 2025 picks batch {i+1} to {output_path}")

if __name__ == "__main__":
    picks_csv = "data/2025_picks.csv"
    output_directory = "data/dynamodb_json_files"
    table_name = "Deadpool"
    
    # Generate JSON files
    process_2025_picks(picks_csv, output_directory, table_name)