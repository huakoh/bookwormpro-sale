#!/bin/bash

# Backend Project Initialization Script
# Usage: ./init_backend_project.sh <project-name> <framework>
# Frameworks: express, fastapi, django, nestjs, flask

set -e

PROJECT_NAME=$1
FRAMEWORK=$2

if [ -z "$PROJECT_NAME" ] || [ -z "$FRAMEWORK" ]; then
    echo "Usage: $0 <project-name> <framework>"
    echo "Supported frameworks: express, fastapi, django, nestjs, flask"
    exit 1
fi

echo "🚀 Initializing backend project: $PROJECT_NAME"
echo "📦 Framework: $FRAMEWORK"

mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# Create base directory structure
mkdir -p src/{config,models,controllers,services,middleware,routes,utils}
mkdir -p tests/{unit,integration}
mkdir -p docs
mkdir -p migrations

case $FRAMEWORK in
    express|nestjs)
        echo "Setting up Node.js project..."
        cat > package.json << 'EOF'
{
  "name": "PROJECT_NAME",
  "version": "1.0.0",
  "description": "Backend API",
  "main": "src/index.js",
  "scripts": {
    "dev": "nodemon src/index.js",
    "start": "node src/index.js",
    "test": "jest",
    "migrate": "node scripts/migrate.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "dotenv": "^16.0.3",
    "cors": "^2.8.5",
    "helmet": "^7.0.0",
    "bcrypt": "^5.1.0",
    "jsonwebtoken": "^9.0.0"
  },
  "devDependencies": {
    "nodemon": "^3.0.1",
    "jest": "^29.5.0"
  }
}
EOF
        sed -i "s/PROJECT_NAME/$PROJECT_NAME/g" package.json
        
        cat > src/index.js << 'EOF'
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
require('dotenv').config();

const app = express();

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
});

// Routes will be imported here

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
});
EOF
        ;;
        
    fastapi|flask)
        echo "Setting up Python project..."
        cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.0
python-dotenv==1.0.0
bcrypt==4.1.1
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
pytest==7.4.3
EOF

        cat > src/main.py << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
EOF
        ;;
        
    django)
        echo "Setting up Django project..."
        cat > requirements.txt << 'EOF'
django==4.2.7
djangorestframework==3.14.0
django-cors-headers==4.3.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
djangorestframework-simplejwt==5.3.0
EOF
        ;;
esac

# Create .env.example
cat > .env.example << 'EOF'
# Server
PORT=3000
NODE_ENV=development

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Authentication
JWT_SECRET=your-secret-key-change-in-production
JWT_EXPIRES_IN=24h

# CORS
ALLOWED_ORIGINS=http://localhost:5173

# External Services (add as needed)
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# STRIPE_SECRET_KEY=
# SENDGRID_API_KEY=
EOF

# Create README
cat > README.md << EOF
# $PROJECT_NAME

Backend API built with $FRAMEWORK

## Setup

1. Install dependencies:
\`\`\`bash
npm install  # or pip install -r requirements.txt
\`\`\`

2. Configure environment:
\`\`\`bash
cp .env.example .env
# Edit .env with your configuration
\`\`\`

3. Run migrations:
\`\`\`bash
npm run migrate  # or python manage.py migrate
\`\`\`

4. Start development server:
\`\`\`bash
npm run dev  # or uvicorn src.main:app --reload
\`\`\`

## API Documentation

See \`docs/API.md\` for endpoint documentation.

## Testing

\`\`\`bash
npm test  # or pytest
\`\`\`
EOF

# Create .gitignore
cat > .gitignore << 'EOF'
node_modules/
__pycache__/
*.pyc
.env
.venv/
venv/
dist/
build/
*.log
.DS_Store
.idea/
.vscode/
*.db
*.sqlite3
coverage/
.pytest_cache/
EOF

echo "✅ Project initialized successfully!"
echo ""
echo "Next steps:"
echo "  1. cd $PROJECT_NAME"
echo "  2. Install dependencies"
echo "  3. Configure .env file"
echo "  4. Start development server"
