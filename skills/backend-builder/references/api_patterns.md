# API Design Patterns Reference

## RESTful API Best Practices

### Resource Naming
- Use plural nouns: `/api/users`, `/api/products`
- Use kebab-case for multi-word resources: `/api/order-items`
- Avoid verbs in URLs (use HTTP methods instead)

### HTTP Methods
- `GET` - Retrieve resources (safe, idempotent)
- `POST` - Create new resources
- `PUT` - Full update (idempotent)
- `PATCH` - Partial update
- `DELETE` - Remove resources (idempotent)

### Standard Endpoints Pattern

```
GET    /api/users              - List all (with pagination)
POST   /api/users              - Create new
GET    /api/users/:id          - Get single
PUT    /api/users/:id          - Full update
PATCH  /api/users/:id          - Partial update
DELETE /api/users/:id          - Delete
GET    /api/users/:id/posts    - Nested resource
```

### Pagination

**Query Parameters:**
```
GET /api/users?page=1&limit=20
GET /api/users?offset=0&limit=20
```

**Response Format:**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

**Cursor-Based (for large datasets):**
```
GET /api/users?cursor=eyJpZCI6MTIzfQ&limit=20

Response:
{
  "data": [...],
  "nextCursor": "eyJpZCI6MTQzfQ",
  "hasMore": true
}
```

### Filtering

```
GET /api/products?category=electronics&price[gte]=100&price[lte]=500
GET /api/users?status=active&role=admin
GET /api/posts?author=123&published=true
```

### Sorting

```
GET /api/products?sort=price          # Ascending
GET /api/products?sort=-price         # Descending (minus prefix)
GET /api/products?sort=category,price # Multiple fields
```

### Searching

```
GET /api/products?q=laptop
GET /api/users?search=john&fields=name,email
GET /api/posts?fulltext=artificial+intelligence
```

### Response Formats

**Success Response:**
```json
{
  "success": true,
  "data": { ... },
  "message": "User created successfully"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Email is required"
      }
    ]
  }
}
```

**List Response:**
```json
{
  "success": true,
  "data": [...],
  "pagination": { ... },
  "meta": {
    "count": 20,
    "total": 150
  }
}
```

### Status Codes

- `200 OK` - Successful GET, PUT, PATCH, DELETE
- `201 Created` - Successful POST
- `204 No Content` - Successful DELETE (no response body)
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Missing/invalid authentication
- `403 Forbidden` - Authenticated but not authorized
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Resource already exists
- `422 Unprocessable Entity` - Validation errors
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

## Authentication Patterns

### JWT Authentication

**Login Endpoint:**
```javascript
POST /api/auth/login
{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "success": true,
  "data": {
    "user": { ... },
    "accessToken": "eyJhbGc...",
    "refreshToken": "eyJhbGc...",
    "expiresIn": 3600
  }
}
```

**Protected Route Header:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Refresh Token:**
```javascript
POST /api/auth/refresh
{
  "refreshToken": "eyJhbGc..."
}

Response:
{
  "accessToken": "eyJhbGc...",
  "expiresIn": 3600
}
```

### API Key Authentication

```
X-API-Key: your-api-key-here
```

### Session-Based Authentication

```javascript
POST /api/auth/login
Response sets cookie:
Set-Cookie: sessionId=abc123; HttpOnly; Secure; SameSite=Strict
```

## Advanced Patterns

### Nested Resources

```
GET /api/users/123/posts           - User's posts
POST /api/users/123/posts          - Create post for user
GET /api/posts/456/comments        - Post's comments
```

### Bulk Operations

```javascript
POST /api/users/bulk
{
  "operation": "create",
  "data": [
    { "name": "User 1", "email": "user1@example.com" },
    { "name": "User 2", "email": "user2@example.com" }
  ]
}

Response:
{
  "success": true,
  "results": [
    { "id": 1, "status": "created" },
    { "id": 2, "status": "created" }
  ],
  "summary": {
    "total": 2,
    "succeeded": 2,
    "failed": 0
  }
}
```

### Batch Requests

```javascript
POST /api/batch
{
  "requests": [
    { "method": "GET", "url": "/api/users/123" },
    { "method": "GET", "url": "/api/posts/456" }
  ]
}

Response:
{
  "responses": [
    { "status": 200, "body": { ... } },
    { "status": 200, "body": { ... } }
  ]
}
```

### Webhooks

```javascript
POST /api/webhooks
{
  "url": "https://example.com/webhook",
  "events": ["user.created", "order.completed"],
  "secret": "webhook-secret"
}
```

### File Upload

**Single File:**
```javascript
POST /api/files
Content-Type: multipart/form-data

Response:
{
  "success": true,
  "data": {
    "id": "file-123",
    "url": "https://cdn.example.com/files/file-123.jpg",
    "size": 1024000,
    "type": "image/jpeg"
  }
}
```

**Presigned URL (for direct upload):**
```javascript
POST /api/files/presign
{
  "filename": "photo.jpg",
  "contentType": "image/jpeg"
}

Response:
{
  "uploadUrl": "https://s3.amazonaws.com/...",
  "fileId": "file-123",
  "expiresIn": 3600
}
```

### Rate Limiting Headers

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

### Versioning

**URL Versioning (recommended):**
```
/api/v1/users
/api/v2/users
```

**Header Versioning:**
```
Accept: application/vnd.api.v2+json
```

**Query Parameter:**
```
/api/users?version=2
```

## GraphQL Patterns

### Query Structure

```graphql
query GetUser($id: ID!) {
  user(id: $id) {
    id
    name
    email
    posts {
      id
      title
      createdAt
    }
  }
}
```

### Mutation Structure

```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    user {
      id
      name
      email
    }
    errors {
      field
      message
    }
  }
}
```

### Pagination (Relay-style)

```graphql
query GetUsers($first: Int, $after: String) {
  users(first: $first, after: $after) {
    edges {
      node {
        id
        name
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

## Error Handling

### Structured Error Codes

```javascript
const ErrorCodes = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR: 'AUTHORIZATION_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  DUPLICATE_RESOURCE: 'DUPLICATE_RESOURCE',
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
  INTERNAL_ERROR: 'INTERNAL_ERROR'
};
```

### Error Response Structure

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "field": "email",
        "code": "INVALID_FORMAT",
        "message": "Email format is invalid"
      }
    ],
    "requestId": "req-123abc"
  }
}
```

## Request/Response Examples

### Create User

```javascript
POST /api/users
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "role": "user"
}

Response (201 Created):
{
  "success": true,
  "data": {
    "id": "user-123",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "user",
    "createdAt": "2024-12-09T10:30:00Z"
  }
}
```

### Update User

```javascript
PATCH /api/users/user-123
Content-Type: application/json

{
  "name": "John Smith"
}

Response (200 OK):
{
  "success": true,
  "data": {
    "id": "user-123",
    "name": "John Smith",
    "email": "john@example.com",
    "updatedAt": "2024-12-09T11:00:00Z"
  }
}
```

### Search with Filters

```javascript
GET /api/products?q=laptop&category=electronics&price[gte]=500&sort=-price&page=1&limit=20

Response (200 OK):
{
  "success": true,
  "data": [
    {
      "id": "prod-1",
      "name": "Gaming Laptop Pro",
      "category": "electronics",
      "price": 1299.99
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "totalPages": 3
  }
}
```

## Security Best Practices

1. **Always validate input** - Use validation libraries (Joi, Zod, Yup)
2. **Sanitize data** - Prevent SQL injection, XSS
3. **Use HTTPS** - Always encrypt in production
4. **Implement rate limiting** - Prevent abuse
5. **Set security headers** - Use helmet.js or equivalent
6. **Validate authentication** - On every protected route
7. **Use prepared statements** - For database queries
8. **Log securely** - Don't log sensitive data
9. **Handle errors safely** - Don't expose internal details
10. **Keep dependencies updated** - Regular security patches
