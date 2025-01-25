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

## Starting the Web Server

```bash
uvicorn src.main:app --reload
```

## API Endpoints

### Base Endpoint

#### Get Available Routes

```
GET /api/v1/deadpool/
```

Returns a list of all available API routes.

Example Response:

```json
{
  "message": "Successfully retrieved available routes",
  "routes": [
    {
      "path": "/api/v1/deadpool/entries/",
      "name": "get_deadpool_data"
    },
    {
      "path": "/api/v1/deadpool/players",
      "name": "get_players"
    }
    // ... other routes
  ]
}
```

### Deadpool Entries

#### Get All Entries

```
GET /api/v1/deadpool/entries/
```

Returns all deadpool entries.

#### Get Single Entry

```
GET /api/v1/deadpool/entries/{entry_id}
```

Returns a specific deadpool entry.

Example:

```
GET /api/v1/deadpool/entries/abc123
```

### Players

#### Get All Players

```
GET /api/v1/deadpool/players
```

Returns all players, optionally filtered by year.

Example:

```
GET /api/v1/deadpool/players?year=2024
```

#### Get Single Player

```
GET /api/v1/deadpool/players/{player_id}
```

Returns a specific player's information, optionally for a specific year.

Example:

```
GET /api/v1/deadpool/players/xyz789?year=2024
```

#### Update Player

```
PUT /api/v1/deadpool/players/{player_id}
```

Updates a player's information.

Example:

```
PUT /api/v1/deadpool/players/xyz789
{
    "name": "John Smith",
    "draft_order": 2,
    "year": 2024,
    "metadata": {
        "team": "Red Sox"
    }
}
```

### People

#### Get All People

```
GET /api/v1/deadpool/people
```

Returns all people in the deadpool.

#### Get Single Person

```
GET /api/v1/deadpool/people/{person_id}
```

Returns a specific person's information.

Example:

```
GET /api/v1/deadpool/people/def456
```

#### Update Person

```
PUT /api/v1/deadpool/people/{person_id}
```

Updates a person's information.

Example:

```
PUT /api/v1/deadpool/people/def456
{
    "name": "Jane Doe",
    "status": "deceased",
    "metadata": {
        "DeathDate": "2024-01-25"
    }
}
```

### Response Format

All endpoints (except the base endpoint) return responses in the following format:

```json
{
    "message": "Success message",
    "data": [...]  // Array of items or single item depending on endpoint
}
```

### Error Responses

- `404 Not Found`: When requested resource doesn't exist
- `500 Internal Server Error`: When database operations fail
