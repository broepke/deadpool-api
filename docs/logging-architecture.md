# Logging Architecture

## Overview
This document outlines the logging architecture for the Deadpool API, designed to provide comprehensive monitoring and troubleshooting capabilities through CloudWatch.

## Components

### 1. Request/Response Middleware
- Log all incoming requests with:
  - Request ID (for tracing)
  - HTTP method and path
  - Query parameters
  - Client IP and user agent
  - Timestamp
- Log all responses with:
  - Request ID (for correlation)
  - Status code
  - Response time
  - Response size

### 2. Database Operation Logging
- Track all DynamoDB operations:
  - Operation type (query, scan, get_item, put_item)
  - Table name
  - Key conditions
  - Execution time
  - Item count
  - Consumed capacity
  - Errors with full context

### 3. Business Event Logging
Track important business events:
- Draft picks
  - Player ID and name
  - Picked person
  - Draft order
  - Timestamp
- Player updates
- Person status changes
- Leaderboard calculations

### 4. Error Tracking
Comprehensive error logging with:
- Error type and message
- Stack trace
- Request context
- User context
- System state

### 5. Performance Metrics
- API endpoint response times
- Database operation latencies
- Resource utilization
- Cache hit/miss rates

## Implementation Details

### Log Format
Structured JSON format for better CloudWatch Insights queries:
```json
{
  "timestamp": "ISO8601 timestamp",
  "request_id": "UUID",
  "level": "INFO|WARNING|ERROR",
  "event_type": "REQUEST|RESPONSE|DB|BUSINESS|ERROR",
  "message": "Human readable message",
  "data": {
    // Event-specific data
  },
  "context": {
    // Additional context
  }
}
```

### Log Levels
- INFO: Normal operations, business events
- WARNING: Potential issues, degraded performance
- ERROR: Failed operations, exceptions
- DEBUG: Detailed debugging information (development only)

### CloudWatch Integration
- Use structured logging for better CloudWatch Insights queries
- Create CloudWatch Metrics from logs
- Set up CloudWatch Alarms for:
  - Error rates
  - Response times
  - Failed operations
  - Resource utilization

### Recommended CloudWatch Insights Queries

1. Find all errors for a request:
```
fields @timestamp, @message
| filter request_id = '<request-id>'
| sort @timestamp desc
```

2. Calculate API endpoint latency:
```
stats avg(response_time) as avg_latency,
      max(response_time) as max_latency
by endpoint
| sort avg_latency desc
```

3. Track draft pick events:
```
filter event_type = 'BUSINESS' and event_name = 'DRAFT_PICK'
| stats count(*) as pick_count by player_id
| sort pick_count desc
```

## Next Steps
1. Create logging utility module
2. Implement FastAPI middleware for request/response logging
3. Add database operation logging to DynamoDBClient
4. Integrate business event logging in router handlers
5. Configure CloudWatch log groups and metrics
6. Set up CloudWatch alarms and dashboards

## Implementation Recommendation
Switch to Code mode to implement the following files:
1. `src/utils/logging.py` - Core logging utility
2. `src/middleware/logging.py` - FastAPI logging middleware
3. Update `src/utils/dynamodb.py` - Add logging to database operations
4. Update `src/routers/deadpool.py` - Add business event logging
5. Update `src/main.py` - Configure logging middleware