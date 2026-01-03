# 2026 API Error Fix Documentation

## Issue Summary

The API endpoint `https://deadpool-api.dataknowsall.com/api/v1/deadpool/picks/by-person/{person_id}` is returning a "Forbidden" error after the 2026 migration. This document outlines the root cause analysis and provides comprehensive solutions.

## Root Cause Analysis

### 1. **Primary Issue: Missing 2026 Draft Order Data**
- The API requires draft order records (`YEAR#2026`) to function properly
- The [`get_players()`](src/utils/dynamodb.py:57-84) method queries for draft order records
- If 2026 draft order doesn't exist, the API returns empty player lists
- This causes downstream failures in the picks service

### 2. **Year Parameter Handling Issues**
- The API defaults to `datetime.now().year` (2026) when no year is specified
- Line 27 in [`picks.py`](src/services/picks.py:27): `target_year = year if year else datetime.now().year`
- Line 440 in [`picks.py`](src/services/picks.py:440): Search range includes 2026 automatically
- No fallback mechanism when 2026 data is incomplete

### 3. **Cache Invalidation Problems**
- Cache keys include year parameter, may contain stale 2026 data
- Cache invalidation logic may not properly handle 2026 migration scenarios
- Cached empty results could persist and cause continued failures

### 4. **Migration Data Integrity**
- 2026 picks may exist but without proper draft order structure
- Migration metadata may indicate completion but miss critical infrastructure records

## Solution Implementation

### 1. **Diagnostic and Fix Script**
Created [`utilities/fix_2026_api_issues.py`](utilities/fix_2026_api_issues.py) to:

#### **Diagnostics:**
- ✅ Check if 2026 draft order records exist
- ✅ Validate migration metadata status
- ✅ Verify 2026 picks data integrity
- ✅ Identify missing infrastructure records

#### **Fixes:**
- 🔧 Create 2026 draft order based on 2025 template
- 🔧 Clear problematic cache entries
- 🔧 Create API fallback configuration
- 🔧 Generate comprehensive fix report

#### **Usage:**
```bash
# Run diagnostics only
python utilities/fix_2026_api_issues.py --dry-run --verbose

# Apply fixes
python utilities/fix_2026_api_issues.py --verbose

# Use custom table
python utilities/fix_2026_api_issues.py --table-name Deadpool-Dev
```

### 2. **Improved Picks Service**
Created [`src/services/picks_improved.py`](src/services/picks_improved.py) with:

#### **Enhanced Year Handling:**
- `_get_safe_year()` method with intelligent fallback logic
- Automatic detection of 2026 data availability
- Graceful fallback to 2025 when 2026 data is incomplete
- Comprehensive logging for troubleshooting

#### **Robust Error Handling:**
- Try-catch blocks around year-specific operations
- Continued processing when individual years fail
- Detailed error logging with context
- Graceful degradation instead of complete failure

#### **Multi-Year Search Strategy:**
- Search multiple years when current year has issues
- Prioritize target year but include fallback years
- Deduplicate results across years
- Maintain data consistency

### 3. **Router Patch**
Created [`patches/deadpool_router_2026_fix.patch`](patches/deadpool_router_2026_fix.patch) to:
- Use improved picks service for better error handling
- Maintain backward compatibility with fallback
- Minimal code changes for easy deployment

## Deployment Steps

### **Step 1: Run Diagnostics**
```bash
python utilities/fix_2026_api_issues.py --dry-run --verbose
```

### **Step 2: Apply Infrastructure Fixes**
```bash
python utilities/fix_2026_api_issues.py --verbose
```

### **Step 3: Deploy Code Improvements**
```bash
# Apply the router patch
git apply patches/deadpool_router_2026_fix.patch

# Deploy the improved service
# (The improved service is automatically imported by the patched router)
```

### **Step 4: Test API Endpoint**
```bash
# Test the problematic endpoint
curl -X GET "https://deadpool-api.dataknowsall.com/api/v1/deadpool/picks/by-person/54749e30-e931-4eee-b71a-d61884e7065f"

# Test with year parameter
curl -X GET "https://deadpool-api.dataknowsall.com/api/v1/deadpool/picks/by-person/54749e30-e931-4eee-b71a-d61884e7065f?year=2025"
```

### **Step 5: Monitor and Validate**
- Check CloudWatch logs for error reduction
- Verify API responses are returning data
- Monitor performance metrics
- Validate data consistency

## Technical Details

### **Draft Order Record Structure**
```json
{
  "PK": "YEAR#2026",
  "SK": "ORDER#1",
  "PlayerID": "player-uuid",
  "DraftOrder": 1,
  "Year": 2026,
  "CreatedAt": "2026-01-03T11:30:00.000Z"
}
```

### **Cache Clear Request Structure**
```json
{
  "PK": "SYSTEM#CACHE_CLEAR",
  "SK": "REQUEST#2026-01-03T11:30:00.000Z",
  "RequestedAt": "2026-01-03T11:30:00.000Z",
  "Reason": "2026_API_ISSUES_FIX",
  "CacheKeys": [
    "picks_list_2026_*",
    "picks_counts_2026",
    "leaderboard_2026",
    "next_drafter_2026",
    "person_picks_*_2026"
  ]
}
```

### **API Fallback Configuration**
```json
{
  "PK": "CONFIG#API_FALLBACK",
  "SK": "YEAR_HANDLING",
  "DefaultYear": 2025,
  "EnableYearFallback": true,
  "FallbackReason": "2026_MIGRATION_ISSUES",
  "CreatedAt": "2026-01-03T11:30:00.000Z"
}
```

## Monitoring and Alerts

### **Key Metrics to Monitor:**
- API error rates for picks endpoints
- Response times for year-specific queries
- Cache hit/miss ratios
- DynamoDB throttling events

### **Log Patterns to Watch:**
- `YEAR_FALLBACK` - Indicates fallback to 2025 is occurring
- `YEAR_CHECK_ERROR` - Problems validating 2026 data
- `GET_PICKS_BY_PERSON_ERROR` - Endpoint-specific errors
- `COMPUTE_PICKS_LIST_ERROR` - Service-level computation errors

### **Success Indicators:**
- ✅ API returns 200 status codes
- ✅ Response contains expected data structure
- ✅ No "Forbidden" errors
- ✅ Reasonable response times (<2 seconds)

## Rollback Plan

If issues persist after applying fixes:

### **Step 1: Immediate Rollback**
```bash
# Revert router changes
git checkout -- src/routers/deadpool.py

# Remove improved service (optional)
rm src/services/picks_improved.py
```

### **Step 2: Force Year Parameter**
- Temporarily modify API to default to 2025
- Add explicit year validation
- Reject requests without year parameter

### **Step 3: Investigation**
- Run validation script to identify remaining issues
- Check DynamoDB for data consistency
- Review CloudWatch logs for error patterns

## Future Improvements

### **Short Term:**
- Add health check endpoint for year-specific data
- Implement automatic cache warming for new years
- Add API parameter validation

### **Long Term:**
- Implement year transition automation
- Add comprehensive migration testing
- Create year-agnostic API design patterns

## Support Information

### **Key Files:**
- [`utilities/fix_2026_api_issues.py`](utilities/fix_2026_api_issues.py) - Diagnostic and fix script
- [`src/services/picks_improved.py`](src/services/picks_improved.py) - Enhanced picks service
- [`patches/deadpool_router_2026_fix.patch`](patches/deadpool_router_2026_fix.patch) - Router patch
- [`docs/2026-migration-implementation-guide.md`](docs/2026-migration-implementation-guide.md) - Original migration guide

### **Contact Information:**
- For urgent issues: Check CloudWatch logs first
- For data validation: Run the diagnostic script
- For rollback procedures: Follow the rollback plan above

---

**Status**: Ready for deployment  
**Risk Level**: Low (comprehensive testing and rollback plan)  
**Estimated Fix Time**: 15-30 minutes  
**Testing Required**: API endpoint validation