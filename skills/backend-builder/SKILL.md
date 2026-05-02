---
name: backend-builder
description: >
safety:
  level: medium
  permissions: [read_file, write_file, terminal]
  后端开发专家。当用户需要 API 开发、数据库设计、Node.js/Express/Fastify/NestJS、
  Python/Django/FastAPI、Go/Gin、Java/Spring Boot 后端开发，RESTful/GraphQL API，
  ORM、JWT 认证、WebSocket，或说 "后端"、"API"、"数据库" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
cost_level: medium
last-reviewed: 2026-02-18
composable: true
  enhances: [database-tuning-expert, api-integration-specialist]
---

# Backend Builder

> **Output Style**: 本技能使用内联输出规范

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 后端开发 | 后端, 后端开发, 服务端, API开发 |
| 框架 | Node.js, Express, FastAPI, NestJS, Django, Go, Gin |
| 微服务 | 微服务, gRPC, protobuf, microservice |
| 数据库 | PostgreSQL, MySQL, MongoDB, Redis |
| API | RESTful, GraphQL, API设计 |

## Overview

Generate production-ready backend systems by analyzing frontend code, UI designs, and workflow diagrams. This skill automatically creates database schemas, API endpoints, authentication systems, and admin panels that seamlessly integrate with your frontend.

## Workflow Decision Tree

**START HERE**: Determine the scope and approach

```
User provides materials?
├─ Frontend code only
│  └─> Analyze API requirements → Generate matching backend
├─ UI design + workflow diagram
│  └─> Extract data model → Design full-stack architecture
├─ Complete spec (frontend + design + workflow)
│  └─> Comprehensive analysis → End-to-end backend generation
└─ Vague request
   └─> Ask for specifics (see Requirement Gathering)
```

## Step 1: Input Analysis

### 1.1 Analyze Frontend Code

When user provides frontend code:

1. **Identify API calls** - Extract all HTTP requests, WebSocket connections, GraphQL queries
2. **Map data structures** - Identify state models, props interfaces, form schemas
3. **Detect auth patterns** - Look for token usage, protected routes, user contexts
4. **List features** - CRUD operations, search, filtering, pagination, file uploads

View frontend code with:
```bash
view /mnt/user-data/uploads/<frontend-file>
```

### 1.2 Parse UI Designs

When user provides UI mockups or design files:

1. **Extract data fields** - Forms, tables, cards, lists showing what data exists
2. **Identify relationships** - Parent-child views, referenced data, linked entities
3. **Note user flows** - Login → Dashboard → CRUD operations
4. **Spot features** - Search bars, filters, sorting, export buttons

For images: Analyze visually for data structures
For Figma/design files: Parse component properties and data bindings

### 1.3 Interpret Workflow Diagrams

When user provides flowcharts or process diagrams:

1. **Map business logic** - Decision points, conditional flows, state transitions
2. **Extract entities** - Boxes/nodes often represent data models
3. **Identify operations** - Actions that need API endpoints
4. **Note triggers** - Events that require webhooks or scheduled jobs

For code-based diagrams (Mermaid, PlantUML): Parse the source
For image diagrams: Analyze visually for logic flow

### 1.4 Requirement Gathering

If inputs are incomplete, ask targeted questions:

```
Missing: Database schema
→ "What data needs to be stored? Can you describe the main entities?"

Missing: Auth requirements
→ "What authentication method? (JWT, OAuth, Session-based)"

Missing: Backend tech stack
→ "Preferred framework? (Node.js/Express, Python/FastAPI, etc.)"

Missing: Deployment target
→ "Where will this deploy? (Cloud provider, containerized, serverless)"
```

## Step 2: Architecture Design

### 2.1 Database Schema Generation

Based on analysis, create normalized database schemas:

**Key principles:**
- Derive entities from UI components and workflow nodes
- Extract fields from forms, tables, API responses
- Identify relationships from navigation and data references
- Add standard fields: `id`, `created_at`, `updated_at`
- Consider soft deletes with `deleted_at`

**Output format:** Generate schema using the `scripts/generate_schema.py` script or write DDL/ORM models directly

Example entity extraction:
```
Frontend component: UserProfileCard
Fields visible: name, email, avatar, role, joinDate
→ Database table: users
   - id (PK)
   - name (string)
   - email (string, unique)
   - avatar_url (string, nullable)
   - role (enum)
   - joined_at (timestamp)
   - created_at, updated_at
```

### 2.2 API Endpoint Design

Generate RESTful or GraphQL APIs matching frontend needs:

**REST API Pattern:**
```
Resource: users
Endpoints detected from frontend:
- GET /api/users (list with pagination)
- GET /api/users/:id (single user)
- POST /api/users (create)
- PUT /api/users/:id (update)
- DELETE /api/users/:id (delete)
- GET /api/users/search?q= (search feature detected)
```

**GraphQL Pattern:**
```graphql
type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type Query {
  users(limit: Int, offset: Int): [User!]!
  user(id: ID!): User
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
}
```

Use `references/api_patterns.md` for advanced API design patterns.

### 2.3 Authentication System

Design auth based on frontend security patterns:

**JWT Pattern (most common):**
- Endpoint: `POST /api/auth/login` → returns access + refresh tokens
- Endpoint: `POST /api/auth/register`
- Endpoint: `POST /api/auth/refresh`
- Middleware: JWT verification on protected routes
- Password: bcrypt hashing with salt rounds

**Session Pattern:**
- Endpoint: `POST /api/auth/login` → sets session cookie
- Session store: Redis or database sessions
- CSRF protection required

**OAuth Pattern:**
- Endpoints: `/api/auth/google`, `/api/auth/github`
- Callback handling with state verification
- Token exchange and user profile mapping

### 2.4 Admin Panel Generation

If admin features detected in UI, generate admin interface:

**Options:**
1. **Use existing admin template** from `assets/admin-templates/`
2. **Generate custom admin** matching brand design
3. **API-only backend** with recommended admin tools (Retool, Forest Admin)

Admin should support:
- CRUD operations for all entities
- User management and roles
- Analytics dashboards (if metrics detected)
- System settings and configuration

## Step 3: Code Generation

### 3.1 Project Structure

Create organized backend structure:

```
backend/
├── src/
│   ├── config/          # Database, environment configs
│   ├── models/          # Database models/schemas
│   ├── controllers/     # Request handlers
│   ├── services/        # Business logic
│   ├── middleware/      # Auth, validation, error handling
│   ├── routes/          # API route definitions
│   └── utils/           # Helper functions
├── tests/               # Unit and integration tests
├── migrations/          # Database migrations
├── .env.example         # Environment variables template
├── package.json         # Dependencies
└── README.md            # Setup instructions
```

### 3.2 Generate Core Files

**Use scripts for boilerplate generation:**
```bash
# Initialize project structure
bash scripts/init_backend_project.sh <project-name> <framework>

# Generate model from schema
python3 scripts/generate_model.py --schema <schema-file> --framework <orm>

# Generate CRUD controller
python3 scripts/generate_controller.py --model <model-name> --routes
```

**For custom logic:** Write controllers that implement:
- Input validation (using Joi, Zod, Pydantic, etc.)
- Error handling with proper HTTP status codes
- Business logic from workflow diagrams
- Data transformations matching frontend expectations

### 3.3 Database Integration

**Generate database setup files:**

For SQL databases, create migration files.
For ORMs (Prisma, TypeORM, SQLAlchemy), generate schema definitions.

**Use reference guides:**
- See `references/database_setup.md` for connection pooling, migration strategies
- See `references/orm_patterns.md` for relationship mapping (when created)

### 3.4 Implement Business Logic

Translate workflow diagrams into code following the diagram's step sequence.
Implement error handling, validation, and transactions for multi-step operations.

## Step 4: Integration & Testing

### 4.1 API Documentation

Generate API docs (OpenAPI/Swagger format) matching frontend requirements.

Use script: `python3 scripts/generate_api_docs.py --routes src/routes/ --output docs/`

### 4.2 Environment Configuration

Create `.env.example` with all required variables:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Authentication
JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=24h

# API
PORT=3000
NODE_ENV=development

# External services (if detected in frontend)
AWS_ACCESS_KEY=
STRIPE_SECRET_KEY=
SENDGRID_API_KEY=
```

### 4.3 Testing Setup

Generate tests for critical paths:

**Unit tests:** Test individual functions, data validation
**Integration tests:** Test API endpoints with database
**E2E tests:** Test complete user flows from frontend perspective

Use `scripts/generate_tests.py` for test boilerplate.

### 4.4 Frontend Integration Guide

Create integration instructions:

```markdown
# Frontend Integration

## 1. Environment Setup
Add to your .env:
```
API_BASE_URL=http://localhost:3000/api
```

## 2. Update API Calls
Replace mock endpoints with real ones:
- `GET /api/users` instead of `/mock/users.json`

## 3. Authentication
Include JWT token in headers:
```javascript
headers: {
  'Authorization': `Bearer ${token}`
}
```
```

## Step 5: Deployment Preparation

Generate deployment configuration:
- Docker files (Dockerfile, docker-compose.yml)
- CI/CD configs (GitHub Actions, GitLab CI)
- Production checklist (env vars, SSL, monitoring, backups)

Use script: `bash scripts/generate_docker.sh --framework <framework> --database <db>`

For detailed deployment strategies, see `references/deployment.md` (when created)

## Advanced Features

For complex backend requirements beyond basic CRUD:

- **Multi-Tenant Architecture** - When workflow indicates multiple organizations need data isolation
  → See `references/advanced_features.md#multi-tenant-architecture`

- **Real-Time Features** - When frontend has WebSocket, live updates, or chat
  → See `references/advanced_features.md#real-time-features`

- **File Upload Handling** - When frontend has file upload forms or image processing
  → See `references/advanced_features.md#file-upload-handling`

- **Background Jobs** - When workflow has async operations (emails, reports, processing)
  → See `references/advanced_features.md#background-jobs`

Auto-detect these patterns from frontend analysis and generate appropriate infrastructure.

## Output Delivery

### File Organization

Place all generated files in organized structure:
```
/home/claude/backend-output/
├── src/                  # Source code
├── tests/                # Test files
├── docs/                 # API documentation
├── scripts/              # Setup and utility scripts
├── .env.example
├── README.md
├── package.json / requirements.txt
└── docker-compose.yml
```

### Deliverables Checklist

Ensure output includes:
- [ ] Complete database schema with migrations
- [ ] All API endpoints implemented
- [ ] Authentication system configured
- [ ] Admin panel (if required)
- [ ] Integration tests
- [ ] API documentation
- [ ] Setup instructions in README
- [ ] Environment configuration template
- [ ] Docker setup for easy deployment
- [ ] Frontend integration guide

### Final Steps

1. **Validate completeness:** Cross-check all frontend requirements are met
2. **Move to outputs:** `cp -r /home/claude/backend-output /mnt/user-data/outputs/`
3. **Generate summary document:** List all files, features, setup steps
4. **Provide next steps:** Testing, deployment, integration instructions

## Common Patterns

Recognize and implement frequently requested application types:

- **CRUD Admin Panel** - List + forms → Full REST API + Admin UI
- **User Authentication** - Login + profile → JWT system + Auth middleware  
- **Dashboard Analytics** - Charts + metrics → Aggregation + Caching
- **E-commerce** - Catalog + cart + checkout → Orders + Payment + Inventory
- **Social Features** - Posts + interactions → Social graph + Activity feeds

For detailed implementations, see `references/common_patterns.md`

## Error Handling

### Common Issues

**Issue:** Frontend API calls don't match generated endpoints
- Verify endpoint paths exactly match frontend expectations
- Check HTTP methods (GET vs POST)
- Validate request/response payload structures

**Issue:** Database schema missing fields
- Re-analyze frontend forms and display components
- Check for computed fields vs stored fields
- Look for hidden fields in UI

**Issue:** Authentication not working
- Verify token format matches frontend expectations
- Check CORS configuration
- Validate token expiration and refresh logic

**Issue:** Relationships missing in schema
- Trace data flow in UI (parent → child views)
- Look for foreign key references in frontend code
- Check for many-to-many relationships in UI

## Best Practices

1. **Always validate inputs** - Never trust frontend data
2. **Use database transactions** - For multi-step operations
3. **Implement proper error handling** - Return meaningful error messages
4. **Add request logging** - For debugging and monitoring
5. **Version your API** - Use `/api/v1/` prefix for future compatibility
6. **Document everything** - Future developers will thank you
7. **Follow security best practices** - OWASP guidelines, principle of least privilege
8. **Optimize queries** - Add indexes for frequent lookups
9. **Implement rate limiting** - Protect against abuse
10. **Write tests first** - Especially for critical business logic

## Resources Referenced

This skill uses bundled resources for complex operations:

- `scripts/init_backend_project.sh` - Project scaffolding
- `scripts/generate_schema.py` - Database schema generation
- `scripts/generate_model.py` - ORM model creation
- `scripts/generate_controller.py` - Controller boilerplate
- `scripts/generate_tests.py` - Test file generation
- `scripts/generate_api_docs.py` - API documentation
- `scripts/generate_docker.sh` - Docker configuration

- `references/api_patterns.md` - Advanced API design patterns
- `references/database_setup.md` - Database configuration guides
- `references/orm_patterns.md` - ORM relationship patterns
- `references/deployment.md` - Deployment strategies
- `references/multi_tenant.md` - Multi-tenant architecture
- `references/realtime.md` - WebSocket and real-time patterns
- `references/background_jobs.md` - Async job processing

- `assets/admin-templates/` - Pre-built admin panel templates

## 项目宪法感知

当工作目录存在 `constitution/AI-CONSTITUTION.md` 时，本技能的交付必须额外遵守:
1. **技术栈锁定**: 检查宪法中的技术栈约束，不引入禁止的框架/依赖
2. **API 契约守护**: 新增/修改端点时检查宪法中的 API 注册表，不破坏已有契约
3. **交付报告**: 输出 `=== AI CODE REVIEW REPORT ===` + `=== CHANGE IMPACT ===`
4. **安全敏感标注**: 涉及 auth/crypto/proxy/payment 模块时标注 `[SECURITY-SENSITIVE]`
