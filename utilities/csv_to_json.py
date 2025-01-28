import pandas as pd
import json
import os

def format_timestamp(timestamp):
    """Format timestamp to ISO 8601 by replacing space with 'T'."""
    if pd.isna(timestamp):
        return None
    return timestamp.replace(" ", "T")

def convert_to_dict(obj):
    """Recursively convert OrderedDict or other nested objects to standard dictionary."""
    if isinstance(obj, dict):
        return {k: convert_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_dict(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_dict(i) for i in obj)
    else:
        return obj

def chunk_list(lst, chunk_size):
    """Split a list into smaller chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def generate_batch_write_json(data, table_name):
    """Format data for DynamoDB batch-write-item JSON structure."""
    # Create the list of PutRequest items and convert everything to plain dictionaries
    put_requests = [{"PutRequest": {"Item": convert_to_dict(item)}} for item in data]
    
    # Split into chunks of 25 items (DynamoDB batch write limit)
    chunked_requests = chunk_list(put_requests, 25)
    
    # Generate a separate file for each chunk
    return [{table_name: chunk} for chunk in chunked_requests]

def process_csvs_to_json(players_csv, people_csv, draft_order_csv, player_picks_csv, output_directory, table_name):
    """Process the CSV files and generate JSON files for each logical DynamoDB section."""
    os.makedirs(output_directory, exist_ok=True)

    table_data = {
        "Players": [],
        "People": [],
        "DraftOrder": [],
        "PlayerPicks": []
    }

    # Process Players
    players_df = pd.read_csv(players_csv)
    for _, row in players_df.iterrows():
        pk = f"PLAYER#{row['ID']}"
        sk = "DETAILS"
        attributes = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "FirstName": {"S": row["FIRST_NAME"]},
            "LastName": {"S": row["LAST_NAME"]},
            # "Email": {"S": row["EMAIL"]},
            # "SMS": {"S": "+" + str(row["SMS"])},
            # "OptIn": {"BOOL": str(row["OPT_IN"]).lower() == "true"},
        }
        table_data["Players"].append(attributes)

    # Process People
    people_df = pd.read_csv(people_csv)
    for _, row in people_df.iterrows():
        pk = f"PERSON#{row['ID']}"
        sk = "DETAILS"
        attributes = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "Name": {"S": row["NAME"]},
            "BirthDate": {"S": row["BIRTH_DATE"]} if not pd.isna(row["BIRTH_DATE"]) else None,
            "DeathDate": {"S": row["DEATH_DATE"]} if not pd.isna(row["DEATH_DATE"]) else None,
            "WikiPage": {"S": row["WIKI_PAGE"]} if not pd.isna(row["WIKI_PAGE"]) else None,
            "WikiID": {"S": row["WIKI_ID"]} if not pd.isna(row["WIKI_ID"]) else None,
            "Age": {"N": str(row["AGE"])} if not pd.isna(row["AGE"]) else None,
        }
        table_data["People"].append({k: v for k, v in attributes.items() if v is not None})

    # Process Draft Order
    draft_order_df = pd.read_csv(draft_order_csv)
    for _, row in draft_order_df.iterrows():
        pk = f"YEAR#{row['YEAR']}"
        sk = f"ORDER#{row['DRAFT_ORDER']}#PLAYER#{row['PLAYER_ID']}"
        attributes = {
            "PK": {"S": pk},
            "SK": {"S": sk},
        }
        table_data["DraftOrder"].append(attributes)

    # Process Player Picks
    player_picks_df = pd.read_csv(player_picks_csv)
    for _, row in player_picks_df.iterrows():
        pk = f"PLAYER#{row['PLAYER_ID']}"
        sk = f"PICK#{row['YEAR']}#{row['PEOPLE_ID']}"
        attributes = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "Year": {"N": str(row["YEAR"])},
            "PersonID": {"S": row["PEOPLE_ID"]},
            "Timestamp": {"S": format_timestamp(row["TIMESTAMP"])},
        }
        table_data["PlayerPicks"].append(attributes)

    # Save each logical section as batch-write compatible JSON files
    for section, data in table_data.items():
        batch_writes = generate_batch_write_json(data, table_name)
        for i, batch in enumerate(batch_writes):
            output_path = os.path.join(output_directory, f"{section}_batch_{i+1}.json")
            # Convert to plain JSON
            with open(output_path, "w") as f:
                json.dump(batch, f, indent=2)
            print(f"Saved {section} batch {i+1} to {output_path}")

# File paths (replace these with your actual file paths)
players_csv = "data/players.csv"
people_csv = "data/people.csv"
draft_order_csv = "data/draft_order.csv"
player_picks_csv = "data/player_picks.csv"
output_directory = "data/dynamodb_json_files"
table_name = "Deadpool"

# Generate JSON files
process_csvs_to_json(players_csv, people_csv, draft_order_csv, player_picks_csv, output_directory, table_name)
