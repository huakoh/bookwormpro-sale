# Advanced Backend Features

This reference provides detailed implementation guidance for advanced backend features beyond basic CRUD operations.

## Multi-Tenant Architecture

### When to Use
When workflow indicates multiple organizations/tenants need to share the same application instance with data isolation.

### Implementation Strategy

#### 1. Database Schema Modifications
Add tenant context to all tables:
```sql
ALTER TABLE users ADD COLUMN tenant_id UUID NOT NULL;
ALTER TABLE posts ADD COLUMN tenant_id UUID NOT NULL;
ALTER TABLE products ADD COLUMN tenant_id UUID NOT NULL;

-- Create index for performance
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_posts_tenant ON posts(tenant_id);
```

#### 2. Tenant Identification Middleware
```javascript
// Express.js
const tenantMiddleware = async (req, res, next) => {
    // Extract tenant from subdomain, header, or token
    const tenant = req.subdomains[0] || 
                   req.headers['x-tenant-id'] ||
                   req.user?.tenantId;
    
    if (!tenant) {
        return res.status(400).json({ error: 'Tenant not specified' });
    }
    
    req.tenant = await Tenant.findById(tenant);
    next();
};
```

#### 3. Tenant-Scoped Queries
```javascript
// Automatically scope all queries to current tenant
class TenantModel {
    static async find(query) {
        return db.query({
            ...query,
            tenant_id: req.tenant.id
        });
    }
}
```

#### 4. Tenant Management API
Generate endpoints for:
- `POST /api/tenants` - Create new tenant
- `GET /api/tenants/:id` - Get tenant info
- `PUT /api/tenants/:id/settings` - Update settings
- `GET /api/tenants/:id/usage` - Usage statistics

## Real-Time Features

### When to Use
When frontend has WebSocket connections, live updates, chat, notifications, or collaborative editing.

### Implementation Options

#### Option 1: Socket.IO (Recommended for Node.js)

**Setup:**
```javascript
const io = require('socket.io')(server, {
    cors: { origin: process.env.FRONTEND_URL }
});

// Authentication
io.use(async (socket, next) => {
    const token = socket.handshake.auth.token;
    const user = await verifyToken(token);
    socket.user = user;
    next();
});

// Handle connections
io.on('connection', (socket) => {
    console.log(`User ${socket.user.id} connected`);
    
    // Join user's room
    socket.join(`user:${socket.user.id}`);
    
    // Handle events
    socket.on('message', async (data) => {
        await Message.create({ ...data, userId: socket.user.id });
        io.to(`room:${data.roomId}`).emit('message', data);
    });
});
```

**Patterns:**
```javascript
// Broadcast to specific user
io.to(`user:${userId}`).emit('notification', data);

// Broadcast to room
io.to(`room:${roomId}`).emit('message', data);

// Broadcast to all except sender
socket.broadcast.emit('user-joined', socket.user);
```

#### Option 2: Server-Sent Events (SSE)

**For one-way updates:**
```javascript
app.get('/api/events', (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    
    const sendEvent = (data) => {
        res.write(`data: ${JSON.stringify(data)}\n\n`);
    };
    
    // Subscribe to events
    eventEmitter.on('update', sendEvent);
    
    req.on('close', () => {
        eventEmitter.off('update', sendEvent);
    });
});
```

#### Option 3: WebSocket (Native)

**For Python FastAPI:**
```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
```

### Connection Management

**Track active connections:**
```javascript
const activeConnections = new Map();

io.on('connection', (socket) => {
    activeConnections.set(socket.user.id, socket);
    
    socket.on('disconnect', () => {
        activeConnections.delete(socket.user.id);
    });
});

// Send to specific user
function notifyUser(userId, event, data) {
    const socket = activeConnections.get(userId);
    if (socket) {
        socket.emit(event, data);
    }
}
```

## File Upload Handling

### When to Use
When frontend has file upload forms, image uploads, document attachments, or bulk imports.

### Implementation Strategy

#### 1. Basic Upload Handler

**Express with Multer:**
```javascript
const multer = require('multer');
const path = require('path');

const storage = multer.diskStorage({
    destination: './uploads/',
    filename: (req, file, cb) => {
        const uniqueName = `${Date.now()}-${file.originalname}`;
        cb(null, uniqueName);
    }
});

const upload = multer({
    storage: storage,
    limits: { fileSize: 5 * 1024 * 1024 }, // 5MB
    fileFilter: (req, file, cb) => {
        const allowedTypes = /jpeg|jpg|png|pdf/;
        const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
        const mimetype = allowedTypes.test(file.mimetype);
        
        if (extname && mimetype) {
            cb(null, true);
        } else {
            cb(new Error('Invalid file type'));
        }
    }
});

app.post('/api/upload', upload.single('file'), async (req, res) => {
    const fileRecord = await File.create({
        filename: req.file.filename,
        originalName: req.file.originalname,
        size: req.file.size,
        mimetype: req.file.mimetype,
        userId: req.user.id
    });
    
    res.json({ success: true, file: fileRecord });
});
```

#### 2. Cloud Storage (AWS S3)

**Direct upload with presigned URLs:**
```javascript
const AWS = require('aws-sdk');
const s3 = new AWS.S3();

app.post('/api/upload/presign', async (req, res) => {
    const { filename, contentType } = req.body;
    const key = `uploads/${req.user.id}/${Date.now()}-${filename}`;
    
    const presignedUrl = s3.getSignedUrl('putObject', {
        Bucket: process.env.S3_BUCKET,
        Key: key,
        ContentType: contentType,
        Expires: 300 // 5 minutes
    });
    
    res.json({
        uploadUrl: presignedUrl,
        fileKey: key
    });
});

// After client uploads to S3
app.post('/api/upload/confirm', async (req, res) => {
    const { fileKey } = req.body;
    
    const fileUrl = `https://${process.env.S3_BUCKET}.s3.amazonaws.com/${fileKey}`;
    
    await File.create({
        key: fileKey,
        url: fileUrl,
        userId: req.user.id
    });
    
    res.json({ success: true, url: fileUrl });
});
```

#### 3. Image Processing

**Resize and optimize:**
```javascript
const sharp = require('sharp');

app.post('/api/upload/image', upload.single('image'), async (req, res) => {
    const processedPath = `processed-${req.file.filename}`;
    
    await sharp(req.file.path)
        .resize(800, 800, { fit: 'inside' })
        .jpeg({ quality: 80 })
        .toFile(path.join('./uploads/', processedPath));
    
    res.json({ 
        original: req.file.filename,
        processed: processedPath 
    });
});
```

#### 4. Multiple File Upload

```javascript
app.post('/api/upload/multiple', upload.array('files', 10), async (req, res) => {
    const files = await Promise.all(
        req.files.map(file => File.create({
            filename: file.filename,
            originalName: file.originalname,
            size: file.size,
            userId: req.user.id
        }))
    );
    
    res.json({ success: true, files });
});
```

### Security Considerations

1. **Validate file types** - Check both extension and MIME type
2. **Limit file size** - Prevent DoS attacks
3. **Scan for malware** - Use ClamAV or similar
4. **Generate unique filenames** - Prevent overwrites
5. **Store outside web root** - Prevent direct access
6. **Implement rate limiting** - Limit uploads per user

## Background Jobs

### When to Use
When workflow has async operations: email sending, report generation, data processing, scheduled tasks.

### Implementation Options

#### Option 1: Bull (Node.js with Redis)

**Setup:**
```javascript
const Queue = require('bull');

const emailQueue = new Queue('email', {
    redis: {
        host: process.env.REDIS_HOST,
        port: process.env.REDIS_PORT
    }
});

// Add job to queue
app.post('/api/send-email', async (req, res) => {
    await emailQueue.add({
        to: req.body.email,
        subject: 'Welcome',
        body: 'Thank you for signing up'
    });
    
    res.json({ success: true, message: 'Email queued' });
});

// Process jobs
emailQueue.process(async (job) => {
    const { to, subject, body } = job.data;
    await sendEmail(to, subject, body);
});

// Handle job events
emailQueue.on('completed', (job) => {
    console.log(`Job ${job.id} completed`);
});

emailQueue.on('failed', (job, err) => {
    console.error(`Job ${job.id} failed:`, err);
});
```

**Job priorities and delays:**
```javascript
// High priority
await emailQueue.add(data, { priority: 1 });

// Delayed job
await emailQueue.add(data, { delay: 60000 }); // 1 minute

// Scheduled job
await emailQueue.add(data, { 
    repeat: { cron: '0 9 * * *' } // Daily at 9 AM
});
```

#### Option 2: Celery (Python)

**Setup:**
```python
from celery import Celery

app = Celery('tasks', broker='redis://localhost:6379')

@app.task
def send_email(to, subject, body):
    # Send email logic
    pass

# Call async
send_email.delay('user@example.com', 'Hello', 'Welcome')

# Call with delay
send_email.apply_async(
    args=['user@example.com', 'Hello', 'Welcome'],
    countdown=60  # 60 seconds
)

# Periodic task
from celery.schedules import crontab

@app.task
def cleanup_old_files():
    # Cleanup logic
    pass

app.conf.beat_schedule = {
    'cleanup-daily': {
        'task': 'cleanup_old_files',
        'schedule': crontab(hour=2, minute=0)
    }
}
```

### Common Job Patterns

#### 1. Email Notifications
```javascript
const sendWelcomeEmail = async (userId) => {
    await emailQueue.add({ userId, template: 'welcome' });
};

const sendDigest = async () => {
    const users = await User.findActiveSubscribers();
    for (const user of users) {
        await emailQueue.add({ 
            userId: user.id, 
            template: 'digest' 
        });
    }
};
```

#### 2. Report Generation
```javascript
const generateReport = async (reportId) => {
    await reportQueue.add({ reportId }, {
        timeout: 300000, // 5 minutes
        attempts: 3
    });
};

reportQueue.process(async (job) => {
    const { reportId } = job.data;
    const data = await fetchReportData(reportId);
    const pdf = await generatePDF(data);
    await uploadToS3(pdf, reportId);
    await Report.update(reportId, { status: 'completed' });
});
```

#### 3. Data Import
```javascript
const importCSV = async (fileId) => {
    await importQueue.add({ fileId }, {
        attempts: 1, // Don't retry
        timeout: 600000 // 10 minutes
    });
};

importQueue.process(async (job) => {
    const { fileId } = job.data;
    const file = await getFile(fileId);
    const rows = await parseCSV(file);
    
    for (let i = 0; i < rows.length; i++) {
        await importRow(rows[i]);
        job.progress((i / rows.length) * 100);
    }
});
```

#### 4. Scheduled Tasks
```javascript
// Daily cleanup
const cleanupQueue = new Queue('cleanup');

cleanupQueue.add({}, {
    repeat: { cron: '0 2 * * *' } // 2 AM daily
});

cleanupQueue.process(async () => {
    await cleanupExpiredSessions();
    await deleteOldLogs();
    await optimizeDatabase();
});
```

### Monitoring and Debugging

**Job status endpoint:**
```javascript
app.get('/api/jobs/:id', async (req, res) => {
    const job = await emailQueue.getJob(req.params.id);
    
    res.json({
        id: job.id,
        progress: job.progress(),
        state: await job.getState(),
        failedReason: job.failedReason,
        finishedOn: job.finishedOn
    });
});

// Queue statistics
app.get('/api/queue/stats', async (req, res) => {
    const [waiting, active, completed, failed] = await Promise.all([
        emailQueue.getWaitingCount(),
        emailQueue.getActiveCount(),
        emailQueue.getCompletedCount(),
        emailQueue.getFailedCount()
    ]);
    
    res.json({ waiting, active, completed, failed });
});
```

### Error Handling

```javascript
emailQueue.process(async (job) => {
    try {
        await sendEmail(job.data);
    } catch (error) {
        // Log error
        console.error(`Job ${job.id} failed:`, error);
        
        // Notify admin on critical errors
        if (error.code === 'SMTP_ERROR') {
            await notifyAdmin(`Email system down: ${error.message}`);
        }
        
        throw error; // Re-throw to mark job as failed
    }
});

// Retry failed jobs
emailQueue.on('failed', async (job, err) => {
    if (job.attemptsMade < 3) {
        await job.retry();
    }
});
```

## Best Practices Summary

1. **Multi-Tenant**: Always validate tenant context, use indexes, implement audit logging
2. **Real-Time**: Handle disconnections gracefully, implement reconnection logic, validate all events
3. **File Upload**: Validate types and sizes, use virus scanning, implement cleanup jobs
4. **Background Jobs**: Set appropriate timeouts, implement retry logic, monitor queue health

## Integration with Main Workflow

When generating backend code, detect these patterns in frontend/UI:
- Multiple organization selector → Multi-tenant
- Live chat/notifications → Real-time
- File upload forms → File handling
- "Process in background" → Background jobs

Auto-generate appropriate infrastructure and endpoints for detected patterns.
