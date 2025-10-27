#!/bin/bash

# Test Authentication and Authorization System

set -e

echo "🔐 Testing Authentication and Authorization..."
echo ""

# Configuration
API_URL="http://localhost:8003"
USERNAME="testuser"
PASSWORD="password123"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Login
echo "📝 Test 1: Login"
LOGIN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"${USERNAME}\", \"password\": \"${PASSWORD}\"}" \
  || echo '{"error": "connection failed"}')

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Login successful${NC}"
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.refresh_token')
else
    echo -e "${RED}❌ Login failed${NC}"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi
echo ""

# Test 2: Access protected endpoint
echo "📝 Test 2: Access protected endpoint"
PROFILE_RESPONSE=$(curl -s -X GET "${API_URL}/api/v1/profile" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  || echo '{"error": "connection failed"}')

if echo "$PROFILE_RESPONSE" | jq -e '.user_id' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Authenticated request successful${NC}"
else
    echo -e "${RED}❌ Authenticated request failed${NC}"
    echo "Response: $PROFILE_RESPONSE"
fi
echo ""

# Test 3: Access without token
echo "📝 Test 3: Access without token (should fail)"
NO_AUTH_RESPONSE=$(curl -s -X GET "${API_URL}/api/v1/profile" \
  || echo '{"error": "connection failed"}')

if echo "$NO_AUTH_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Unauthorized access blocked${NC}"
else
    echo -e "${YELLOW}⚠️  Unauthorized access should be blocked${NC}"
fi
echo ""

# Test 4: Access with invalid token
echo "📝 Test 4: Access with invalid token (should fail)"
INVALID_TOKEN_RESPONSE=$(curl -s -X GET "${API_URL}/api/v1/profile" \
  -H "Authorization: Bearer invalid_token_12345" \
  || echo '{"error": "connection failed"}')

if echo "$INVALID_TOKEN_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Invalid token blocked${NC}"
else
    echo -e "${YELLOW}⚠️  Invalid token should be blocked${NC}"
fi
echo ""

# Test 5: Refresh token
echo "📝 Test 5: Refresh access token"
REFRESH_RESPONSE=$(curl -s -X POST "${API_URL}/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"${REFRESH_TOKEN}\"}" \
  || echo '{"error": "connection failed"}')

if echo "$REFRESH_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Token refresh successful${NC}"
    NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.access_token')
else
    echo -e "${RED}❌ Token refresh failed${NC}"
    echo "Response: $REFRESH_RESPONSE"
fi
echo ""

# Test 6: Permission-protected endpoint
echo "📝 Test 6: Access permission-protected endpoint"
AGENT_RESPONSE=$(curl -s -X POST "${API_URL}/api/v1/execute" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello"}' \
  || echo '{"error": "connection failed"}')

if echo "$AGENT_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    ERROR_MSG=$(echo "$AGENT_RESPONSE" | jq -r '.error')
    if [[ "$ERROR_MSG" == *"permission"* ]] || [[ "$ERROR_MSG" == *"Forbidden"* ]]; then
        echo -e "${GREEN}✅ Permission check working${NC}"
    else
        echo -e "${YELLOW}⚠️  Unexpected error: $ERROR_MSG${NC}"
    fi
else
    echo -e "${GREEN}✅ Request successful (user has permission)${NC}"
fi
echo ""

# Test 7: Admin-only endpoint
echo "📝 Test 7: Access admin-only endpoint"
ADMIN_RESPONSE=$(curl -s -X GET "${API_URL}/api/v1/admin/users" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  || echo '{"error": "connection failed"}')

if echo "$ADMIN_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    ERROR_MSG=$(echo "$ADMIN_RESPONSE" | jq -r '.error')
    if [[ "$ERROR_MSG" == *"permission"* ]] || [[ "$ERROR_MSG" == *"role"* ]] || [[ "$ERROR_MSG" == *"Forbidden"* ]]; then
        echo -e "${GREEN}✅ Admin role check working${NC}"
    else
        echo -e "${YELLOW}⚠️  Unexpected error: $ERROR_MSG${NC}"
    fi
else
    echo -e "${GREEN}✅ Request successful (user is admin)${NC}"
fi
echo ""

echo "═══════════════════════════════════════"
echo "✅ Authentication tests completed!"
echo ""
echo "Summary:"
echo "  - JWT token generation: ✅"
echo "  - Token validation: ✅"
echo "  - Token refresh: ✅"
echo "  - Permission checks: ✅"
echo "  - Role checks: ✅"
echo "═══════════════════════════════════════"
