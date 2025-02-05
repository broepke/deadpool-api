To implement the backend phone number validation, submit this task:

"Implement phone number validation in the API for the profile update endpoint. Requirements:

1. Input Validation:
   - Require E.164 format (+12223334444)
   - Must start with + followed by country code
   - Total length 11-15 digits after +
   - Only digits allowed after +
   - Required format regex: /^\+[1-9]\d{10,14}$/

2. Data Cleaning:
   - Strip any whitespace, hyphens, or parentheses
   - Remove any non-digit characters except leading +
   - Normalize to E.164 format

3. Business Rules:
   - If no country code provided, assume +1 (US)
   - Reject numbers with invalid country codes
   - Maximum length validation (15 digits after +)
   - Minimum length validation (11 digits after +)

4. Error Responses:
   - 400 Bad Request for format violations
   - Clear error messages specifying the issue
   - Example error response:
     ```json
     {
       \"error\": \"invalid_phone\",
       \"message\": \"Phone number must be in E.164 format (+12223334444)\",
       \"details\": \"Missing + prefix\"
     }
     ```

5. Success Response:
   - Return normalized E.164 format
   - Set phone_verified to false if number changed
   - Example response:
     ```json
     {
       \"phone_number\": \"+12223334444\",
       \"phone_verified\": false
     }
     ```

This ensures consistent phone number handling across the entire application."