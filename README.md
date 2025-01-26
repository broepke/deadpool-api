# deadpool-api

## AWS Lambda Deployment

The API can be deployed as an AWS Lambda function using the provided deployment script.

### Prerequisites

- AWS CLI installed and configured with appropriate credentials
- Python 3.9 or later
- Access to the AWS Lambda function "Deadpool-app"

### Deployment Steps

1. Deploy using the automated script:

   ```bash
   ./utilities/deploy_lambda.sh
   ```

   This script will:

   - Clean up any previous deployment artifacts
   - Install dependencies in a temporary directory
   - Create a deployment package (lambda_function.zip)
   - Upload the package to AWS Lambda
   - Clean up temporary files

2. (Optional) Configure the Lambda function:

   - Handler: `src.main.handler`
   - Runtime: Python 3.9
   - Memory: 256 MB (recommended)
   - Timeout: 30 seconds

   You can uncomment the configuration section in the deployment script to automate these settings.

### API Gateway Integration

The API is configured to work with API Gateway using:
- Stage: /default
- Base path: /api/v1/deadpool
- Example endpoint: https://[api-id].execute-api.[region].amazonaws.com/default/api/v1/deadpool/players

Configuration requirements:
- Use Lambda Proxy integration
- Forward all requests to the Lambda function
- Handle CORS if needed (already configured in the application)

Note: The Mangum handler in lambda_function.py is configured with api_gateway_base_path="/default" to match the API Gateway stage.

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

```json
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

```json
GET /api/v1/deadpool/players
```

Returns all players, optionally filtered by year.

Example:

```json
GET /api/v1/deadpool/players?year=2024
```

#### Get Single Player

```json
GET /api/v1/deadpool/players/{player_id}
```

Returns a specific player's information, optionally for a specific year.

Example:

```json
GET /api/v1/deadpool/players/xyz789?year=2024
```

#### Create or Update Player

```json
PUT /api/v1/deadpool/players/{player_id}
```

Creates a new player or updates an existing player's information. When creating a new player, the following fields are required:

- `name`: Player's full name
- `draft_order`: Player's draft position
- `year`: Draft year

Example creating a new player:

```json
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

Example updating an existing player:

```json
PUT /api/v1/deadpool/players/xyz789
{
    "metadata": {
        "team": "Yankees"
    }
}
```

### People

#### Get All People

```json
GET /api/v1/deadpool/people
```

Returns all people in the deadpool.

#### Get Single Person

```json
GET /api/v1/deadpool/people/{person_id}
```

Returns a specific person's information.

Example:

```json
GET /api/v1/deadpool/people/def456
```

#### Create or Update Person

```json
PUT /api/v1/deadpool/people/{person_id}
```

Creates a new person or updates an existing person's information. When creating a new person, the following field is required:

- `name`: Person's full name

To create a new person with an automatically generated UUID, use "new" as the person_id:

```json
PUT /api/v1/deadpool/people/new
{
    "name": "Jane Doe",
    "metadata": {
        "Age": 75,
        "BirthDate": "1949-01-25"
    }
}
```

The response will include the generated UUID in the person's "id" field.

Example updating an existing person's status:

```json
PUT /api/v1/deadpool/people/def456
{
    "status": "deceased",
    "metadata": {
        "DeathDate": "2024-01-25"
    }
}
```

### Draft Order

#### Get Draft Order Records

```json
GET /api/v1/deadpool/draft-order
```

Returns draft order records, optionally filtered by year and/or player.

Example:

```json
GET /api/v1/deadpool/draft-order?year=2024
GET /api/v1/deadpool/draft-order?player_id=xyz789
GET /api/v1/deadpool/draft-order?year=2024&player_id=xyz789
```

#### Update Draft Order

```json
PUT /api/v1/deadpool/draft-order/{player_id}
```

Updates a player's draft order for a specific year.

Example:

```json
PUT /api/v1/deadpool/draft-order/xyz789?year=2024&draft_order=3
```

### Player Picks

#### Draft a Person

```json
POST /api/v1/deadpool/draft
```

Creates a new draft pick for a player. This endpoint will:

1. Verify the person hasn't been picked in the current year
2. Create a new person entry if they don't exist in the database
3. Create a player pick entry with the current timestamp

Required request body:

```json
{
  "name": "Jane Doe",
  "player_id": "xyz789"
}
```

Example response:

```json
{
  "message": "Successfully processed draft request",
  "data": {
    "person_id": "8b3b23bc-be64-4b7d-949d-8080a5267ed5",
    "name": "Jane Doe",
    "is_new": true,
    "pick_timestamp": "2025-01-25T23:45:18Z"
  }
}
```

Example CURL:

```bash
# BRIAN'S ID

curl -X POST \
  'http://localhost:8000/api/v1/deadpool/draft' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Jane Doe",
    "player_id": "1831699b-e255-45ff-8671-b5c840922735"
  }'


# ANDREW'S ID

curl -X POST \
  'http://localhost:8000/api/v1/deadpool/draft' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Jane Doe",
    "player_id": "bc913bed-5795-441d-916b-2a778383858e"
  }'
```

The endpoint will return:

- 404 error if the drafting player doesn't exist
- 400 error if the person was already drafted in the current year

#### Get All Picks with Details

```json
GET /api/v1/deadpool/picks
```

Returns all picks for a given year with detailed information about both players and their picked persons. Results are sorted by draft order.

Required query parameter:

- `year`: Filter picks by year

Example:

```json
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

```json
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

```json
GET /api/v1/deadpool/player-picks/{player_id}
```

Returns all picks made for a specific player, optionally filtered by year. Results are sorted by timestamp with most recent picks first.

Example:

```json
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

### Leaderboard

#### Get Leaderboard

```json
GET /api/v1/deadpool/leaderboard
```

Returns a ranked list of players based on their scores for a given year. The score for each player is calculated as the sum of `50 + (100 - Age)` for each of their celebrity picks that are deceased (have a DeathDate).

Optional query parameter:

- `year`: Filter by year (defaults to current year if not specified)

Example:

```json
GET /api/v1/deadpool/leaderboard
GET /api/v1/deadpool/leaderboard?year=2024
```

Response format:

```json
{
  "message": "Successfully retrieved leaderboard",
  "data": [
    {
      "player_id": "xyz789",
      "player_name": "John Smith",
      "score": 250
    },
    {
      "player_id": "abc123",
      "player_name": "Jane Doe",
      "score": 175
    }
    // ... other players sorted by score (highest first)
  ]
}
```

The response includes:

- `player_id`: The ID of the player
- `player_name`: The name of the player
- `score`: Total score calculated from their dead celebrity picks

### Draft Order Management

#### Get Next Drafter

```json
GET /api/v1/deadpool/draft-next
```

Determines who should draft next based on the following criteria:

1. Lowest draft order number for the current year
2. Least number of picks for the current year
3. Total picks not exceeding 20 for active people (where DeathDate is null)

Example Response:

```json
{
  "message": "Successfully determined next drafter",
  "data": {
    "player_id": "xyz789",
    "player_name": "John Smith",
    "draft_order": 1,
    "current_pick_count": 5,
    "active_pick_count": 5
  }
}
```

The response includes:

- `player_id`: The ID of the next player to draft
- `player_name`: The name of the next player to draft
- `draft_order`: Their current draft order position
- `current_pick_count`: Total number of picks they have for the current year
- `active_pick_count`: Number of picks they have for people who are still alive

### Response Format

All endpoints (except the base endpoint) return responses in the following format:

```json
{
    "message": "Success message",
    "data": [...]  // Array of items or single item depending on endpoint
}
```

### Error Responses

- `400 Bad Request`: When required fields are missing for new records
- `404 Not Found`: When requested resource doesn't exist
- `500 Internal Server Error`: When database operations fail
