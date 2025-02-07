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

- Stages: /dev and /prod
- Base path: /api/v1/deadpool
- Dev Endpoint: [https://deadpool-api-dev.dataknowsall.com](https://deadpool-api-dev.dataknowsall.com)
- Prod Endpoint: [https://deadpool-api.dataknowsall.com](https://deadpool-api.dataknowsall.com)

Configuration requirements:

- Use Lambda Proxy integration
- Forward all requests to the Lambda function

#### CORS Configuration

CORS is configured at the API Gateway level using stage variables to support different origins for development and production environments.

1. Stage Variables Setup:

   - Dev Stage:
     - Name: `allowOrigin`
     - Value: `http://localhost:5173`
   - Prod Stage:
     - Name: `allowOrigin`
     - Value: `https://deadpool.dataknowsall.com`

2. CORS Configuration for Each Resource:

   - In Integration Response:
     - Remove all Header Mappings
     - Add Response Template (application/json):

     ```text
     #set($origin = $stageVariables.allowOrigin)
     #set($context.responseOverride.header.Access-Control-Allow-Origin = $origin)
     #set($context.responseOverride.header.Access-Control-Allow-Headers = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Requested-With,Accept")
     #set($context.responseOverride.header.Access-Control-Allow-Methods = "GET,OPTIONS")
     #set($context.responseOverride.header.Access-Control-Allow-Credentials = "true")
     #set($context.responseOverride.header.Access-Control-Expose-Headers = "Content-Length,Content-Type,*")
     #set($context.responseOverride.header.Access-Control-Max-Age = "300")
     {}
     ```

3. Method Response:
   - Configure response headers:
     - Access-Control-Allow-Origin
     - Access-Control-Allow-Methods
     - Access-Control-Allow-Headers
     - Access-Control-Allow-Credentials
     - Access-Control-Expose-Headers
     - Access-Control-Max-Age

**This configuration allows:**

- Development testing from localhost
- Production access from the main domain
- Proper handling of API key authentication
- Pre-flight OPTIONS requests
- Credentials in cross-origin requests

Note: The Mangum handler in lambda_function.py is configured without api_gateway_base_path to support multiple stages.

## DynamoDB PartiQL Queries

Find all people who are not deceased

```sql
SELECT * FROM "Deadpool" 
WHERE begins_with(PK, 'PERSON#')
AND SK = 'DETAILS'
AND attribute_not_exists(DeathDate)
```

## CloudWatch Insights Queries

The following CloudWatch Insights queries are useful for monitoring and troubleshooting the API:

### 1. Monitor Draft Success Rate

```text
filter event_type like 'DRAFT' and data.year = 2025
| stats count(*) as total,
    count(event_type = 'DRAFT_COMPLETE') as successes,
    count(level = 'ERROR') as failures,
    (count(event_type = 'DRAFT_COMPLETE') * 100.0 / count(*)) as success_rate
| sort success_rate desc
```

### 2. Track API Performance by Endpoint

```text
filter event_type = 'RESPONSE'
| stats
    avg(data.elapsed_ms) as avg_latency_ms,
    max(data.elapsed_ms) as max_latency_ms,
    min(data.elapsed_ms) as min_latency_ms
by data.path, data.method
| display data.path, data.method, avg_latency_ms, max_latency_ms, min_latency_ms
| sort request_count desc
```

```text
filter event_type = 'RESPONSE'
| stats count(*) as count by data.status_code, data.path, data.method
| sort data.path, data.method, count desc
```

### 3. Monitor Player Draft Activity

```text
filter event_type = 'DRAFT_COMPLETE' and data.year = 2025
| stats count(*) as pick_count,
    avg(data.elapsed_ms) as avg_pick_time_ms,
    count_distinct(data.person_id) as unique_picks,
    max(data.pick_timestamp) as latest_pick
by data.player_id, data.player_name
| sort pick_count desc
```

### 4. Track Leaderboard Updates

```text
filter event_type = 'LEADERBOARD_PLAYER' and data.year = 2025
| stats latest(data.score) as current_score,
    latest(data.dead_picks) as dead_picks,
    latest(data.total_picks) as total_picks,
    latest(data.player_name) as player_name
by data.player_id
| sort current_score desc
```

### 5. Error Analysis

```text
filter level = 'ERROR'
| stats count(*) as error_count,
    count_distinct(request_id) as affected_requests,
    earliest(data.elapsed_ms) as first_occurrence_ms,
    latest(data.elapsed_ms) as last_occurrence_ms,
    latest(error.type) as error_type,
    latest(error.message) as error_message
by event_type
| sort error_count desc
```

These queries help with:

- Monitoring API health and performance
- Tracking game progress and player activity
- Identifying potential issues
- Analyzing error patterns
- Making data-driven improvements

## Data Migration Flow: CSV to DynamoDB

This repository includes a data migration pipeline that transforms CSV data into DynamoDB records. The process involves two main steps:

### 1. DynamoDB Table Creation

The following command will create the proper DynamoDB table structure.

```bash
aws dynamodb create-table \
    --table-name Deadpool \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST
```

### 2. CSV to JSON Conversion (utilities/csv_to_json.py)

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

### 3. DynamoDB Loading (utilities/bulk_load_dynamodb.sh)

The shell script handles the actual data loading:

- Uses AWS CLI's `batch-write-item` command
- Processes each batch file sequentially
- Loads data in sections: Players, People, DraftOrder, and PlayerPicks

### 4. Running the Migration

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

## Name Matching System

The API uses a robust fuzzy name matching system to handle variations in celebrity name entries. This system helps prevent duplicate entries and improves draft pick accuracy.

### Name Matching Features

- Case-insensitive matching
- Punctuation normalization (removing/standardizing periods, commas)
- Suffix standardization (Jr./Jr, /, III/3, etc.)
- Fuzzy matching using the RapidFuzz algorithm

### Configuration Parameters

The name matching system is configured with the following parameters (located in `src/utils/name_matching.py`):

```python
NAME_MATCHING_CONFIG = {
    'similarity_threshold': 0.85,  # Minimum similarity score to consider a match
    'min_length_for_fuzzy': 4,    # Minimum name length to apply fuzzy matching
    'suffix_map': {               # Standardization mappings
        'jr.': 'jr',
        'sr.': 'sr',
        'junior': 'jr',
        'senior': 'sr',
        'iii': '3',
        'ii': '2'
    }
}
```

- `similarity_threshold` (0.85): Names with a similarity score ≥ 85% are considered matches
- `min_length_for_fuzzy` (4): Names shorter than 4 characters skip fuzzy matching and require exact matches
- `suffix_map`: Standardizes common name suffixes for consistent matching

### How It Works

1. **Name Normalization**

   - Converts to lowercase
   - Removes/standardizes punctuation
   - Standardizes multiple spaces
   - Normalizes common suffixes

2. **Matching Process**

   - First checks for exact matches after normalization
   - For names ≥ 4 characters, applies fuzzy matching
   - Calculates similarity score using RapidFuzz ratio
   - Returns match details including similarity score

3. **Match Results**
   Returns a dictionary with:
   - `match`: Boolean indicating if names are considered a match
   - `similarity`: Float score between 0 and 1
   - `normalized1`: Normalized version of first name
   - `normalized2`: Normalized version of second name
   - `exact_match`: Boolean indicating exact match after normalization

This system is particularly useful in the draft endpoint where it helps prevent duplicate celebrity entries with slightly different spellings.

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

#### Update Player Profile

```json
PUT /api/v1/deadpool/players/{player_id}/profile
```

Updates a player's profile information. This endpoint allows updating personal details and notification preferences.

Fields that can be updated:
- `first_name`: Player's first name
- `last_name`: Player's last name
- `phone_number`: Player's phone number
- `phone_verified`: Whether the phone number is verified
- `sms_notifications_enabled`: Whether SMS notifications are enabled
- `metadata`: Additional metadata key-value pairs

Example updating a player's profile:

```json
PUT /api/v1/deadpool/players/xyz789/profile
{
    "first_name": "John",
    "last_name": "Smith",
    "phone_number": "+1234567890",
    "sms_notifications_enabled": true,
    "metadata": {
        "team": "Red Sox"
    }
}
```

Response:

```json
{
    "message": "Successfully updated player profile"
}
```

All fields are optional - only the fields that need to be updated need to be included in the request.

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

Returns a paginated list of people in the deadpool. Supports filtering by status and optional pagination or limit.

Optional query parameters:
- `status`: Filter by status ('deceased' or 'alive')
- `page_size`: Number of items per page (default: 10, max: 100)
- `page`: Page number for paginated results (default: 1)
- `limit`: Alternative to pagination, returns a specific number of items

When status=deceased is specified, results are sorted by death date in descending order (most recent first).

Examples:

```json
# Default pagination (10 items per page)
GET /api/v1/deadpool/people

# Filter by status with custom page size
GET /api/v1/deadpool/people?status=deceased&page_size=20

# Get specific page of alive people
GET /api/v1/deadpool/people?status=alive&page=2&page_size=20

# Use limit instead of pagination
GET /api/v1/deadpool/people?limit=50
```

Response format:

```json
{
  "message": "Successfully retrieved people",
  "data": [
    {
      "id": "8b3b23bc-be64-4b7d-949d-8080a5267ed5",
      "name": "Jane Doe",
      "status": "deceased",
      "metadata": {
        "Age": 75,
        "BirthDate": "1949-01-25",
        "DeathDate": "2024-01-25"
      }
    }
    // ... other people
  ],
  "total": 55,         // Total number of items available
  "page": 1,           // Current page number
  "page_size": 10,     // Number of items per page
  "total_pages": 6     // Total number of pages
}
```

Note: The pagination metadata (total, page, page_size, total_pages) is always included in the response, even when using the limit parameter. When using limit, page will be 1 and total_pages will be 1.

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

Returns picks for a given year with detailed information about both players and their picked persons. Results are sorted by draft order.

#### Get Picks by Person

```json
GET /api/v1/deadpool/picks/by-person/{person_id}
```

Returns all picks for a specific person across all players. This endpoint is particularly useful for finding out who picked a specific celebrity.

Optional query parameters:
- `year`: Filter picks by year (defaults to current year)
- `page_size`: Number of items per page (default: 10, max: 100)
- `page`: Page number for paginated results (default: 1)
- `limit`: Alternative to pagination, returns a specific number of items

Examples:

```json
# Get all picks for a specific person in the current year
GET /api/v1/deadpool/picks/by-person/8b3b23bc-be64-4b7d-949d-8080a5267ed5

# Get picks for a specific person in a particular year
GET /api/v1/deadpool/picks/by-person/8b3b23bc-be64-4b7d-949d-8080a5267ed5?year=2024

# Use limit instead of pagination
GET /api/v1/deadpool/picks/by-person/8b3b23bc-be64-4b7d-949d-8080a5267ed5?limit=5
```

Response format:

```json
{
  "message": "Successfully retrieved picks",
  "data": [
    {
      "player_id": "xyz789",
      "player_name": "John Smith",
      "draft_order": 1,
      "pick_person_id": "8b3b23bc-be64-4b7d-949d-8080a5267ed5",
      "pick_person_name": "Jane Doe",
      "pick_person_age": 75,
      "pick_person_birth_date": "1949-01-25",
      "pick_person_death_date": "2024-01-25",
      "pick_timestamp": "2024-01-01T12:00:00",
      "year": 2024
    }
    // ... other picks for this person
  ],
  "total": 3,          // Total number of picks for this person
  "page": 1,           // Current page number
  "page_size": 10,     // Number of items per page
  "total_pages": 1     // Total number of pages
}
```

The response includes detailed information about:
- Who picked the person (player_name)
- When they were picked (pick_timestamp)
- Person details (name, age, birth/death dates)
- Year of the pick

Results are sorted by pick timestamp in descending order (most recent first).

Required query parameter:
- `year`: Filter picks by year

Optional query parameters:
- `page_size`: Number of items per page (default: 10, max: 100)
- `page`: Page number for paginated results (default: 1)
- `limit`: Alternative to pagination, returns a specific number of items

Examples:

```json
# Default pagination (10 items per page)
GET /api/v1/deadpool/picks?year=2024

# Custom page size
GET /api/v1/deadpool/picks?year=2024&page_size=20

# Get specific page
GET /api/v1/deadpool/picks?year=2024&page=2&page_size=20

# Use limit instead of pagination
GET /api/v1/deadpool/picks?year=2024&limit=50
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
  ],
  "total": 55,         // Total number of items available
  "page": 1,           // Current page number
  "page_size": 10,     // Number of items per page
  "total_pages": 6     // Total number of pages
}
```

Note: The pagination metadata (total, page, page_size, total_pages) is always included in the response, even when using the limit parameter. When using limit, page will be 1 and total_pages will be 1.

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

### Pick Counts

#### Get Pick Counts

```json
GET /api/v1/deadpool/picks-counts
```

Returns a count of picks for each player in a given year. Results are sorted by draft order.

Optional query parameter:

- `year`: Filter by year (defaults to current year if not specified)

Example:

```json
GET /api/v1/deadpool/picks-counts
GET /api/v1/deadpool/picks-counts?year=2024
```

Response format:

```json
{
  "message": "Successfully retrieved pick counts",
  "data": [
    {
      "player_id": "54e804d8-4061-7010-013c-870d2ef43041",
      "player_name": "Chris Vienneau",
      "draft_order": 1,
      "pick_count": 4,
      "year": 2025
    }
    // ... other players sorted by draft order
  ]
}
```

The response includes:

- `player_id`: The ID of the player
- `player_name`: The name of the player
- `draft_order`: Their draft order position
- `pick_count`: Number of picks they have for the specified year
- `year`: The year the counts are for

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
