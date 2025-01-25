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
      "path": "/api/v1/deadpool/people/",
      "name": "get_people"
    },
    {
      "path": "/api/v1/deadpool/players",
      "name": "get_players"
    }
    // ... other routes
  ]
}
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

### Draft Order

#### Get Draft Order Records

```
GET /api/v1/deadpool/draft-order
```

Returns draft order records, optionally filtered by year and/or player.

Example:

```
GET /api/v1/deadpool/draft-order?year=2024
GET /api/v1/deadpool/draft-order?player_id=xyz789
GET /api/v1/deadpool/draft-order?year=2024&player_id=xyz789
```

#### Update Draft Order

```
PUT /api/v1/deadpool/draft-order/{player_id}
```

Updates a player's draft order for a specific year.

Example:

```
PUT /api/v1/deadpool/draft-order/xyz789?year=2024&draft_order=3
```

### Player Picks

#### Get All Picks with Details

```
GET /api/v1/deadpool/picks
```

Returns all picks for a given year with detailed information about both players and their picked persons. Results are sorted by draft order.

Required query parameter:
- `year`: Filter picks by year

Example:

```
GET /api/v1/deadpool/picks?year=2024
```

Response format:
```json
{
    "message": "Successfully retrieved picks",
    "data": [
        {
            "player_id": "0f7bc0ea-6704-491d-8fe0-5a015a9851c9",
            "player_name": "John Wholihan",
            "draft_order": 1,
            "pick_person_id": "17a406cb-9706-4632-821c-8882c4efd5a8",
            "pick_person_name": "Carrot Top",
            "pick_person_age": 58,
            "pick_person_birth_date": "1965-02-25",
            "pick_person_death_date": null,
            "pick_timestamp": "2024-01-13T18:21:29.307000",
            "year": 2024
        }
        // ... other picks
    ]
}
```

#### Update Player Pick

```
PUT /api/v1/deadpool/player-picks/{player_id}
```

Creates or updates a pick for a specific player. The timestamp is automatically set to the current time.

Example:

```json
PUT /api/v1/deadpool/player-picks/xyz789
{
    "person_id": "8b3b23bc-be64-4b7d-949d-8080a5267ed5",
    "year": 2024
}
```

#### Get Player Picks

```
GET /api/v1/deadpool/player-picks/{player_id}
```

Returns all picks made for a specific player, optionally filtered by year. Results are sorted by timestamp with most recent picks first.

Example:

```
GET /api/v1/deadpool/player-picks/xyz789
GET /api/v1/deadpool/player-picks/xyz789?year=2024
```

Response format:
```json
{
    "message": "Successfully retrieved player picks",
    "data": [
        {
            "person_id": "8b3b23bc-be64-4b7d-949d-8080a5267ed5",
            "year": 2024,
            "timestamp": "2024-01-12T02:12:13.343"
        }
        // ... other picks
    ]
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
