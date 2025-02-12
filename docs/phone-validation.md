# Phone Validation Implementation Plan

## Overview
Implement phone number validation for player profiles using AWS SNS for sending verification codes and managing subscriptions.

## Current Infrastructure
- DynamoDB schema supports phone verification (PhoneNumber and PhoneVerified attributes)
- Existing `/api/v1/deadpool/players/{player_id}/profile` endpoint for profile updates
- PlayerProfileUpdate model includes phone_number and phone_verified fields

## Implementation Plan

### 1. SNS Utility Module
Create `src/utils/sns.py` with the following functions:
```python
def generate_verification_code():
    """Generate a 6-digit verification code"""
    return str(random.randint(100000, 999999))

def send_verification_code(phone_number: str, code: str) -> str:
    """Send verification code via SNS"""
    # Initialize SNS client
    # Send SMS with code
    # Return message ID

def manage_sns_subscription(phone_number: str, subscribe: bool = True) -> Optional[str]:
    """Manage SNS topic subscription"""
    # Subscribe/unsubscribe phone number to notifications topic
    # Return subscription ARN or None
```

### 2. New API Endpoints

#### 2.1 Request Verification Code
```
POST /api/v1/deadpool/players/{player_id}/phone/request-verification
Request:
{
    "phone_number": string  // E.164 format (+1234567890)
}
Response:
{
    "message": string,
    "data": {
        "message_id": string,
        "expires_at": string  // ISO timestamp
    }
}
```

#### 2.2 Verify Code
```
POST /api/v1/deadpool/players/{player_id}/phone/verify
Request:
{
    "code": string  // 6-digit code
}
Response:
{
    "message": string,
    "data": {
        "verified": boolean,
        "subscription_arn": string  // SNS subscription ARN
    }
}
```

### 3. New Pydantic Models

```python
class PhoneVerificationRequest(BaseModel):
    phone_number: str

class PhoneVerificationResponse(BaseModel):
    message: str
    data: Dict[str, Any]

class CodeVerificationRequest(BaseModel):
    code: str

class CodeVerificationResponse(BaseModel):
    message: str
    data: Dict[str, Any]
```

### 4. DynamoDB Schema Updates
Add the following attributes to the Player entity:
- `verification_code`: (Optional) String - Temporary verification code
- `verification_timestamp`: (Optional) String - ISO timestamp of when code was generated

### 5. Verification Flow
1. User requests verification code:
   - Validate phone number format
   - Generate verification code
   - Store code and timestamp in user's profile
   - Send code via SNS
   - Return message ID and expiration time

2. User submits verification code:
   - Validate code hasn't expired
   - Compare with stored code
   - If valid:
     - Update PhoneVerified status
     - Subscribe to notifications topic
     - Clear stored verification data
   - Return verification result

### 6. Error Handling
- Invalid phone number format (must be E.164 format)
- Rate limiting for code requests (max 3 attempts per 10 minutes)
- Code expiration (10 minutes from verification_timestamp)
- Invalid/expired codes
- SNS service errors
- DynamoDB operation errors
- Clear verification data after successful verification or max attempts

### 7. Security Considerations
- Rate limit verification attempts
- Expire verification codes after 10 minutes
- Validate phone number format (E.164)
- Secure storage of verification codes
- Access control for verification endpoints

### 7. Testing
- Unit tests for SNS utilities
- Integration tests for API endpoints
- Test cases for error scenarios
- Test rate limiting
- Test code expiration

## Next Steps
1. Create SNS utility module
2. Add new Pydantic models
3. Implement API endpoints
4. Add error handling
5. Write tests
6. Update documentation

## Dependencies
- boto3 for AWS SNS integration
- Existing FastAPI infrastructure
- DynamoDB for data storage
- AWS credentials configuration

## Notes
- Consider implementing a separate verification codes table in DynamoDB
- May need to update IAM roles for SNS access
- Consider adding phone number validation regex
- Plan for handling international phone numbers