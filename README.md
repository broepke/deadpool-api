# deadpool-api

## Data Migration Flow: CSV to DynamoDB

This repository includes a data migration pipeline that transforms CSV data into DynamoDB records. The process involves two main steps:

### 1. CSV to JSON Conversion (utilities/csv_to_json.py)

The Python script processes four source CSV files:

- `data/players.csv`: Player information including contact details and opt-in status
- `data/people.csv`: Celebrity data including birth/death dates and Wikipedia references
- `data/draft_order.csv`: Annual draft order assignments
- `data/player_picks.csv`: Player selections with timestamps

The script:

- Converts CSV records into DynamoDB-compatible JSON format
- Properly formats data types (String, Number, Boolean)
- Structures data using composite keys (PK/SK) for efficient querying
- Splits data into batches of 25 items (DynamoDB batch write limit)
- Outputs JSON files to `data/dynamodb_json_files/` directory

### 2. DynamoDB Loading (utilities/bulk_load_dynamodb.sh)

The shell script handles the actual data loading:

- Uses AWS CLI's `batch-write-item` command
- Processes each batch file sequentially
- Loads data in sections: Players, People, DraftOrder, and PlayerPicks

### Running the Migration

1. Ensure your CSV files are in the `data/` directory
2. Convert CSV to JSON:

   ```bash
   python utilities/csv_to_json.py
   ```

3. Load data into DynamoDB:

   ```bash
   ./utilities/bulk_load_dynamodb.sh
   ```

Note: Ensure you have AWS credentials configured with appropriate permissions to write to DynamoDB.


## 

Starting the Web Server:

```bash
cd src && uvicorn main:app --reload
```