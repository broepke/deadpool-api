# DynamoDB Schema Design

## Status
Accepted

## Context
The Deadpool application needs to store and manage several related entities:
- Players (participants in the game)
- People (potential picks that players can choose)
- Draft Orders (the order in which players make their picks for each year)
- Player Picks (the actual picks made by players)

We need a schema design that efficiently supports our access patterns while maintaining data consistency and minimizing costs.

## Decision
We will use a single-table design in DynamoDB with composite primary keys (Partition Key - PK and Sort Key - SK) to model different entity types and their relationships.

### Primary Key Patterns

#### Players
- PK: `PLAYER#{player_id}`
- SK: `DETAILS`
- Attributes:
  - Type: "Player"
  - FirstName: string
  - LastName: string
  - PhoneNumber: string (optional)
  - PhoneVerified: boolean
  - SmsNotificationsEnabled: boolean

#### People (Potential Picks)
- PK: `PERSON#{person_id}`
- SK: `DETAILS`
- Attributes:
  - Type: "Person"
  - Name: string
  - DeathDate: string (optional, presence indicates deceased status)
  - Additional metadata fields as needed

#### Draft Orders
- PK: `YEAR#{year}`
- SK: `ORDER#{draft_order}#PLAYER#{player_id}`
- Attributes:
  - Type: "DraftOrder"

#### Player Picks
- PK: `PLAYER#{player_id}`
- SK: `PICK#{year}#{person_id}`
- Attributes:
  - Year: number
  - PersonID: string
  - Timestamp: string (ISO format)

### Access Patterns

1. Get Player Details
   ```
   PK = PLAYER#{player_id}
   SK = DETAILS
   ```

2. Get Person Details
   ```
   PK = PERSON#{person_id}
   SK = DETAILS
   ```

3. Get Draft Order for a Year
   ```
   PK = YEAR#{year}
   SK begins_with ORDER#
   ```

4. Get Player's Picks
   ```
   PK = PLAYER#{player_id}
   SK begins_with PICK#
   Optional filter by year: SK begins_with PICK#{year}#
   ```

5. Get All People
   ```
   Scan with filter:
   SK = DETAILS AND begins_with(PK, PERSON#)
   Optional status filter:
   - Deceased: attribute_exists(DeathDate)
   - Alive: attribute_not_exists(DeathDate)
   ```

### Data Types and Relationships

1. Player Entity
   - Represents a participant in the game
   - Contains profile information and communication preferences
   - Related to picks through the player_id
   - Related to draft order through the player_id

2. Person Entity
   - Represents a potential pick
   - Contains basic information and status (alive/deceased)
   - Related to picks through the person_id

3. Draft Order Entity
   - Represents the order of picks for a specific year
   - Combines year, draft position, and player information
   - Enables efficient retrieval of draft order by year

4. Player Pick Entity
   - Represents a player's pick of a person
   - Contains timestamp for tracking pick order
   - Combines player, person, and year information

## Consequences

### Advantages
1. Efficient queries for common access patterns
   - Get all picks for a player
   - Get draft order for a year
   - Get player/person details

2. Strong consistency for related data
   - Draft orders are atomic per year
   - Picks are atomic per player

3. Flexible schema for metadata
   - Additional attributes can be added to entities without schema changes
   - Supports varying data requirements for different entity types

4. Cost-effective storage and retrieval
   - Minimizes the need for table scans
   - Uses composite keys for efficient data organization

### Disadvantages
1. Some operations require table scans
   - Getting all people requires a scan with filters
   - Could impact performance with large datasets

2. Complex key structures
   - Composite sort keys require careful parsing
   - Need to maintain consistent key formats

3. Limited secondary indexes
   - Relies on primary key patterns for most access patterns
   - May require additional GSIs for new access patterns

## Implementation Notes

1. Key Formatting
   - Consistent delimiter usage (#) in composite keys
   - Clear prefix patterns (PLAYER#, PERSON#, etc.)
   - Year-based partitioning for draft orders

2. Data Consistency
   - Use transactions for related updates when necessary
   - Maintain consistent attribute naming conventions
   - Handle optional attributes gracefully

3. Error Handling
   - Implement robust error handling for key parsing
   - Validate input data before storage
   - Handle missing or incomplete records gracefully