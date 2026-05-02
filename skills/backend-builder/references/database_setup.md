# Database Setup and Configuration

## Connection Strategies

### PostgreSQL Connection

**Node.js with pg:**
```javascript
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

module.exports = pool;
```

**Python with psycopg2:**
```python
import psycopg2
from psycopg2 import pool

connection_pool = psycopg2.pool.SimpleConnectionPool(
    1, 20,
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
```

### Connection Pooling Best Practices

1. **Pool size** - Set based on concurrent requests (typically 10-20)
2. **Idle timeout** - Release idle connections (30s recommended)
3. **Connection timeout** - Fail fast on connection issues (2s)
4. **Health checks** - Test connections before use

## Migration Strategies

### Node.js Migration Tools

**Using node-pg-migrate:**
```javascript
// migrations/1234567890_create_users.js
exports.up = pgm => {
  pgm.createTable('users', {
    id: 'uuid',
    email: { type: 'varchar(255)', unique: true, notNull: true },
    password_hash: { type: 'varchar(255)', notNull: true },
    created_at: {
      type: 'timestamp',
      notNull: true,
      default: pgm.func('current_timestamp'),
    },
  });
  
  pgm.createIndex('users', 'email');
};

exports.down = pgm => {
  pgm.dropTable('users');
};
```

**Using Knex.js:**
```javascript
exports.up = function(knex) {
  return knex.schema.createTable('users', table => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('email').unique().notNull();
    table.string('password_hash').notNull();
    table.timestamps(true, true);
  });
};

exports.down = function(knex) {
  return knex.schema.dropTable('users');
};
```

### Python Migration Tools

**Using Alembic (with SQLAlchemy):**
```python
# alembic/versions/001_create_users.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_users_email', 'users', ['email'])

def downgrade():
    op.drop_table('users')
```

## Schema Design Patterns

### Timestamps Pattern

Always include standard timestamp fields:
```sql
created_at TIMESTAMP DEFAULT NOW() NOT NULL,
updated_at TIMESTAMP DEFAULT NOW() NOT NULL
```

Trigger for auto-updating `updated_at`:
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

### Soft Delete Pattern

```sql
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP NULL;
CREATE INDEX idx_users_deleted_at ON users(deleted_at);

-- Query only active records
SELECT * FROM users WHERE deleted_at IS NULL;

-- Soft delete
UPDATE users SET deleted_at = NOW() WHERE id = ?;
```

### UUID vs Auto-increment IDs

**UUID advantages:**
- Globally unique
- Secure (non-sequential)
- Distributed system friendly

**Auto-increment advantages:**
- Smaller storage
- Better index performance
- Easier debugging

**PostgreSQL UUID setup:**
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4()
);
```

### Enum Types

**PostgreSQL enums:**
```sql
CREATE TYPE user_role AS ENUM ('admin', 'user', 'guest');

CREATE TABLE users (
    id UUID PRIMARY KEY,
    role user_role NOT NULL DEFAULT 'user'
);
```

**Alternative: Check constraints:**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    CONSTRAINT valid_role CHECK (role IN ('admin', 'user', 'guest'))
);
```

## Indexing Strategies

### Common Index Types

**B-tree (default):**
```sql
CREATE INDEX idx_users_email ON users(email);
```

**Unique index:**
```sql
CREATE UNIQUE INDEX idx_users_email ON users(email);
```

**Composite index:**
```sql
CREATE INDEX idx_posts_author_date ON posts(author_id, created_at DESC);
```

**Partial index:**
```sql
CREATE INDEX idx_active_users ON users(email) WHERE deleted_at IS NULL;
```

**Full-text search:**
```sql
CREATE INDEX idx_posts_search ON posts USING GIN(to_tsvector('english', title || ' ' || content));
```

### When to Add Indexes

✅ Add indexes for:
- Foreign keys
- Columns in WHERE clauses
- Columns in ORDER BY
- Columns in JOIN conditions
- Unique constraints

❌ Avoid indexes on:
- Small tables (<1000 rows)
- Columns with low cardinality
- Columns that are frequently updated

## Relationship Patterns

### One-to-Many

```sql
CREATE TABLE authors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL
);

CREATE TABLE books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    author_id UUID REFERENCES authors(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(id)
);

CREATE INDEX idx_books_author ON books(author_id);
```

### Many-to-Many

```sql
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL
);

CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL
);

CREATE TABLE enrollments (
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (student_id, course_id)
);

CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
```

### Self-Referencing (Tree Structure)

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES categories(id) ON DELETE SET NULL
);

CREATE INDEX idx_categories_parent ON categories(parent_id);
```

## Database Functions and Procedures

### Stored Procedure Example

```sql
CREATE OR REPLACE FUNCTION create_user_with_profile(
    p_email VARCHAR,
    p_password VARCHAR,
    p_name VARCHAR
) RETURNS UUID AS $$
DECLARE
    v_user_id UUID;
BEGIN
    INSERT INTO users (email, password_hash)
    VALUES (p_email, crypt(p_password, gen_salt('bf')))
    RETURNING id INTO v_user_id;
    
    INSERT INTO profiles (user_id, name)
    VALUES (v_user_id, p_name);
    
    RETURN v_user_id;
END;
$$ LANGUAGE plpgsql;
```

### Trigger Example

```sql
CREATE OR REPLACE FUNCTION log_user_changes()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (table_name, record_id, action, changed_at)
    VALUES ('users', NEW.id, TG_OP, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION log_user_changes();
```

## Performance Optimization

### Query Optimization

**Use EXPLAIN ANALYZE:**
```sql
EXPLAIN ANALYZE
SELECT * FROM users WHERE email = 'user@example.com';
```

**Avoid N+1 queries:**
```javascript
// Bad
const users = await User.findAll();
for (const user of users) {
    const posts = await Post.findAll({ where: { userId: user.id } });
}

// Good
const users = await User.findAll({
    include: [{ model: Post }]
});
```

### Connection Pool Tuning

```javascript
const pool = new Pool({
    max: 20,                    // Maximum connections
    min: 5,                     // Minimum connections
    idleTimeoutMillis: 30000,   // Close idle after 30s
    connectionTimeoutMillis: 2000,
    statement_timeout: 10000,   // Query timeout 10s
});
```

### Caching Strategy

**Application-level cache (Redis):**
```javascript
const cacheKey = `user:${userId}`;
let user = await redis.get(cacheKey);

if (!user) {
    user = await db.query('SELECT * FROM users WHERE id = $1', [userId]);
    await redis.setex(cacheKey, 3600, JSON.stringify(user));
}
```

**Database query cache:**
```sql
-- PostgreSQL: Use materialized views for expensive queries
CREATE MATERIALIZED VIEW user_stats AS
SELECT 
    user_id,
    COUNT(*) as post_count,
    MAX(created_at) as last_post_at
FROM posts
GROUP BY user_id;

-- Refresh periodically
REFRESH MATERIALIZED VIEW user_stats;
```

## Backup and Recovery

### Backup Script (PostgreSQL)

```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR="/backups"
DB_NAME="myapp_db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup
pg_dump -U postgres -d $DB_NAME | gzip > $BACKUP_FILE

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

### Point-in-Time Recovery

```bash
# Enable WAL archiving in postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /archive/%f'

# Restore to specific point
pg_restore -d myapp_db -t "2024-12-09 10:30:00" backup.sql
```

## Multi-Database Setup

### Read Replicas

```javascript
const masterPool = new Pool({
    connectionString: process.env.MASTER_DB_URL,
    max: 20
});

const replicaPool = new Pool({
    connectionString: process.env.REPLICA_DB_URL,
    max: 50  // More connections for read-heavy load
});

// Write operations
async function createUser(data) {
    return masterPool.query('INSERT INTO users...', [data]);
}

// Read operations
async function getUsers() {
    return replicaPool.query('SELECT * FROM users...');
}
```

### Sharding Strategy

```javascript
function getShardId(userId) {
    // Hash-based sharding
    return parseInt(userId, 16) % NUM_SHARDS;
}

function getPool(shardId) {
    return pools[shardId];
}

// Usage
const shardId = getShardId(userId);
const pool = getPool(shardId);
await pool.query('SELECT...', [userId]);
```

## Security Considerations

### SQL Injection Prevention

```javascript
// ❌ NEVER DO THIS
const query = `SELECT * FROM users WHERE email = '${email}'`;

// ✅ ALWAYS USE PARAMETERIZED QUERIES
const query = 'SELECT * FROM users WHERE email = $1';
await pool.query(query, [email]);
```

### Encryption at Rest

```sql
-- Enable pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt sensitive data
INSERT INTO users (email, ssn_encrypted)
VALUES ('user@example.com', pgp_sym_encrypt('123-45-6789', 'encryption_key'));

-- Decrypt when needed
SELECT email, pgp_sym_decrypt(ssn_encrypted, 'encryption_key') 
FROM users;
```

### Row-Level Security (PostgreSQL)

```sql
-- Enable RLS
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY user_posts_policy ON posts
    FOR ALL
    USING (author_id = current_setting('app.current_user_id')::uuid);

-- Set user context in application
await pool.query("SET app.current_user_id = $1", [userId]);
```
