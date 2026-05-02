# Common Backend Patterns

Detailed implementation guides for frequently requested application types.

## Pattern 1: CRUD Admin Panel

### Recognition Signals
Frontend shows: List view + Create form + Edit form + Delete button

### Implementation

#### Database Schema
```sql
CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

CREATE INDEX idx_items_status ON items(status);
CREATE INDEX idx_items_deleted ON items(deleted_at);
```

#### REST API Endpoints
```javascript
// List with pagination, filtering, sorting
GET /api/items?page=1&limit=20&status=active&sort=-createdAt

// Create
POST /api/items
Body: { name, description, status }

// Read
GET /api/items/:id

// Update
PUT /api/items/:id
Body: { name, description, status }

// Delete (soft)
DELETE /api/items/:id
```

#### Controller Implementation (Express)
```javascript
const itemController = {
    // List with filters
    async list(req, res) {
        const { page = 1, limit = 20, status, sort = '-createdAt' } = req.query;
        
        const query = { deleted_at: null };
        if (status) query.status = status;
        
        const items = await Item.find(query)
            .sort(sort)
            .skip((page - 1) * limit)
            .limit(limit);
        
        const total = await Item.countDocuments(query);
        
        res.json({
            data: items,
            pagination: {
                page: parseInt(page),
                limit: parseInt(limit),
                total,
                totalPages: Math.ceil(total / limit)
            }
        });
    },
    
    // Create with validation
    async create(req, res) {
        const { name, description, status } = req.body;
        
        if (!name) {
            return res.status(400).json({ error: 'Name is required' });
        }
        
        const item = await Item.create({ name, description, status });
        res.status(201).json({ data: item });
    },
    
    // Update
    async update(req, res) {
        const item = await Item.findByIdAndUpdate(
            req.params.id,
            req.body,
            { new: true, runValidators: true }
        );
        
        if (!item) {
            return res.status(404).json({ error: 'Item not found' });
        }
        
        res.json({ data: item });
    },
    
    // Soft delete
    async delete(req, res) {
        const item = await Item.findByIdAndUpdate(
            req.params.id,
            { deleted_at: new Date() },
            { new: true }
        );
        
        if (!item) {
            return res.status(404).json({ error: 'Item not found' });
        }
        
        res.json({ message: 'Item deleted successfully' });
    }
};
```

#### Admin UI Integration
Generate admin interface with:
- Searchable data table
- Create/Edit modal forms
- Bulk actions (delete, export)
- Status filters
- Date range selectors

## Pattern 2: User Authentication Flow

### Recognition Signals
Frontend has: Login page + Protected routes + User profile + Password reset

### Implementation

#### Database Schema
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'user',
    email_verified BOOLEAN DEFAULT FALSE,
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_reset_token ON users(reset_token);
```

#### Authentication API
```javascript
// Register
POST /api/auth/register
Body: { email, password, firstName, lastName }
Response: { user, accessToken, refreshToken }

// Login
POST /api/auth/login
Body: { email, password }
Response: { user, accessToken, refreshToken }

// Refresh token
POST /api/auth/refresh
Body: { refreshToken }
Response: { accessToken }

// Logout
POST /api/auth/logout
Headers: Authorization: Bearer <token>

// Forgot password
POST /api/auth/forgot-password
Body: { email }

// Reset password
POST /api/auth/reset-password
Body: { token, newPassword }

// Get current user
GET /api/auth/me
Headers: Authorization: Bearer <token>
Response: { user }
```

#### JWT Implementation
```javascript
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');

// Register
async register(req, res) {
    const { email, password, firstName, lastName } = req.body;
    
    // Check if user exists
    const existing = await User.findOne({ email });
    if (existing) {
        return res.status(409).json({ error: 'Email already registered' });
    }
    
    // Hash password
    const passwordHash = await bcrypt.hash(password, 10);
    
    // Create user
    const user = await User.create({
        email,
        password_hash: passwordHash,
        first_name: firstName,
        last_name: lastName
    });
    
    // Generate tokens
    const accessToken = jwt.sign(
        { userId: user.id, email: user.email },
        process.env.JWT_SECRET,
        { expiresIn: '15m' }
    );
    
    const refreshToken = jwt.sign(
        { userId: user.id },
        process.env.JWT_REFRESH_SECRET,
        { expiresIn: '7d' }
    );
    
    res.status(201).json({
        user: { id: user.id, email: user.email, firstName, lastName },
        accessToken,
        refreshToken
    });
}

// Login
async login(req, res) {
    const { email, password } = req.body;
    
    const user = await User.findOne({ email });
    if (!user) {
        return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
        return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    // Update last login
    await User.updateOne({ _id: user.id }, { last_login: new Date() });
    
    // Generate tokens (same as register)
    // ...
    
    res.json({ user, accessToken, refreshToken });
}

// Auth middleware
const authMiddleware = async (req, res, next) => {
    const token = req.headers.authorization?.split(' ')[1];
    
    if (!token) {
        return res.status(401).json({ error: 'No token provided' });
    }
    
    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.user = await User.findById(decoded.userId);
        next();
    } catch (error) {
        return res.status(401).json({ error: 'Invalid token' });
    }
};
```

#### Password Reset Flow
```javascript
const crypto = require('crypto');

// Request reset
async forgotPassword(req, res) {
    const { email } = req.body;
    const user = await User.findOne({ email });
    
    if (!user) {
        // Don't reveal if email exists
        return res.json({ message: 'If email exists, reset link sent' });
    }
    
    // Generate reset token
    const resetToken = crypto.randomBytes(32).toString('hex');
    const expires = new Date(Date.now() + 3600000); // 1 hour
    
    await User.updateOne(
        { _id: user.id },
        { reset_token: resetToken, reset_token_expires: expires }
    );
    
    // Send email with reset link
    await sendEmail(user.email, 'Password Reset', 
        `Reset your password: ${process.env.FRONTEND_URL}/reset?token=${resetToken}`
    );
    
    res.json({ message: 'If email exists, reset link sent' });
}

// Reset password
async resetPassword(req, res) {
    const { token, newPassword } = req.body;
    
    const user = await User.findOne({
        reset_token: token,
        reset_token_expires: { $gt: new Date() }
    });
    
    if (!user) {
        return res.status(400).json({ error: 'Invalid or expired token' });
    }
    
    const passwordHash = await bcrypt.hash(newPassword, 10);
    
    await User.updateOne(
        { _id: user.id },
        { 
            password_hash: passwordHash,
            reset_token: null,
            reset_token_expires: null
        }
    );
    
    res.json({ message: 'Password reset successfully' });
}
```

## Pattern 3: Dashboard with Analytics

### Recognition Signals
Frontend shows: Charts + Metrics cards + Filters + Date range selector

### Implementation

#### Aggregation Queries
```javascript
// Total users over time
const getUserGrowth = async (startDate, endDate) => {
    return await User.aggregate([
        {
            $match: {
                created_at: { $gte: startDate, $lte: endDate }
            }
        },
        {
            $group: {
                _id: { $dateToString: { format: "%Y-%m-%d", date: "$created_at" } },
                count: { $sum: 1 }
            }
        },
        { $sort: { _id: 1 } }
    ]);
};

// Revenue by category
const getRevenueByCategory = async () => {
    return await Order.aggregate([
        { $match: { status: 'completed' } },
        {
            $lookup: {
                from: 'products',
                localField: 'product_id',
                foreignField: '_id',
                as: 'product'
            }
        },
        { $unwind: '$product' },
        {
            $group: {
                _id: '$product.category',
                total: { $sum: '$amount' }
            }
        }
    ]);
};
```

#### Dashboard API
```javascript
GET /api/dashboard/stats
Query: { startDate, endDate, metric }

Response: {
    summary: {
        totalUsers: 1250,
        activeUsers: 450,
        revenue: 125000,
        orders: 340
    },
    charts: {
        userGrowth: [...],
        revenueByCategory: [...],
        ordersByStatus: [...]
    }
}
```

#### Caching Strategy
```javascript
const redis = require('redis');
const client = redis.createClient();

const getDashboardStats = async (req, res) => {
    const cacheKey = `dashboard:${req.query.startDate}:${req.query.endDate}`;
    
    // Check cache
    const cached = await client.get(cacheKey);
    if (cached) {
        return res.json(JSON.parse(cached));
    }
    
    // Compute stats
    const stats = {
        summary: await getSummaryStats(),
        charts: await getChartData()
    };
    
    // Cache for 5 minutes
    await client.setex(cacheKey, 300, JSON.stringify(stats));
    
    res.json(stats);
};
```

## Pattern 4: E-commerce System

### Recognition Signals
Frontend has: Product catalog + Cart + Checkout + Order history

### Implementation

#### Database Schema
```sql
-- Products
CREATE TABLE products (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INTEGER DEFAULT 0,
    category VARCHAR(100),
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Shopping carts
CREATE TABLE carts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE cart_items (
    id UUID PRIMARY KEY,
    cart_id UUID REFERENCES carts(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL
);

-- Orders
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    payment_status VARCHAR(50) DEFAULT 'pending',
    shipping_address TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    product_id UUID REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL
);
```

#### Checkout Flow
```javascript
// Add to cart
POST /api/cart/items
Body: { productId, quantity }

// Update cart item
PUT /api/cart/items/:id
Body: { quantity }

// Remove from cart
DELETE /api/cart/items/:id

// Checkout
POST /api/checkout
Body: { shippingAddress, paymentMethod }

// Process order
1. Validate cart items
2. Check inventory
3. Process payment
4. Create order
5. Update inventory
6. Clear cart
7. Send confirmation email
```

#### Transaction Implementation
```javascript
const checkout = async (req, res) => {
    const session = await mongoose.startSession();
    session.startTransaction();
    
    try {
        // Get cart
        const cart = await Cart.findOne({ user_id: req.user.id })
            .populate('items.product');
        
        // Check inventory
        for (const item of cart.items) {
            if (item.product.stock_quantity < item.quantity) {
                throw new Error(`Insufficient stock for ${item.product.name}`);
            }
        }
        
        // Calculate total
        const totalAmount = cart.items.reduce(
            (sum, item) => sum + (item.price * item.quantity), 0
        );
        
        // Process payment
        const payment = await processPayment({
            amount: totalAmount,
            method: req.body.paymentMethod
        });
        
        // Create order
        const order = await Order.create([{
            user_id: req.user.id,
            total_amount: totalAmount,
            status: 'confirmed',
            payment_status: payment.status,
            shipping_address: req.body.shippingAddress
        }], { session });
        
        // Create order items and update inventory
        for (const item of cart.items) {
            await OrderItem.create([{
                order_id: order[0].id,
                product_id: item.product.id,
                quantity: item.quantity,
                price: item.price
            }], { session });
            
            await Product.updateOne(
                { _id: item.product.id },
                { $inc: { stock_quantity: -item.quantity } },
                { session }
            );
        }
        
        // Clear cart
        await Cart.deleteOne({ _id: cart.id }, { session });
        
        await session.commitTransaction();
        
        // Send confirmation email (outside transaction)
        await sendOrderConfirmation(req.user.email, order[0]);
        
        res.json({ order: order[0] });
        
    } catch (error) {
        await session.abortTransaction();
        res.status(400).json({ error: error.message });
    } finally {
        session.endSession();
    }
};
```

## Pattern 5: Social Features

### Recognition Signals
Frontend shows: Posts + Comments + Likes + Follow/Unfollow buttons + Activity feed

### Implementation

#### Database Schema
```sql
-- Posts
CREATE TABLE posts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    image_url VARCHAR(500),
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Comments
CREATE TABLE comments (
    id UUID PRIMARY KEY,
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Likes
CREATE TABLE likes (
    user_id UUID REFERENCES users(id),
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- Follows
CREATE TABLE follows (
    follower_id UUID REFERENCES users(id),
    following_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);

CREATE INDEX idx_posts_user ON posts(user_id, created_at DESC);
CREATE INDEX idx_follows_follower ON follows(follower_id);
CREATE INDEX idx_follows_following ON follows(following_id);
```

#### Activity Feed Implementation
```javascript
// Get personalized feed
const getFeed = async (req, res) => {
    const userId = req.user.id;
    const { page = 1, limit = 20 } = req.query;
    
    // Get posts from followed users + own posts
    const posts = await Post.aggregate([
        {
            $lookup: {
                from: 'follows',
                localField: 'user_id',
                foreignField: 'following_id',
                as: 'follows'
            }
        },
        {
            $match: {
                $or: [
                    { user_id: userId },
                    { 'follows.follower_id': userId }
                ]
            }
        },
        {
            $lookup: {
                from: 'users',
                localField: 'user_id',
                foreignField: '_id',
                as: 'author'
            }
        },
        {
            $lookup: {
                from: 'likes',
                let: { postId: '$_id' },
                pipeline: [
                    { $match: { $expr: { $and: [
                        { $eq: ['$post_id', '$$postId'] },
                        { $eq: ['$user_id', userId] }
                    ]}}}
                ],
                as: 'userLike'
            }
        },
        { $sort: { created_at: -1 } },
        { $skip: (page - 1) * limit },
        { $limit: limit },
        {
            $project: {
                content: 1,
                image_url: 1,
                likes_count: 1,
                comments_count: 1,
                created_at: 1,
                author: { $arrayElemAt: ['$author', 0] },
                isLiked: { $gt: [{ $size: '$userLike' }, 0] }
            }
        }
    ]);
    
    res.json({ posts });
};

// Like/Unlike post
const toggleLike = async (req, res) => {
    const { postId } = req.params;
    const userId = req.user.id;
    
    const existing = await Like.findOne({ user_id: userId, post_id: postId });
    
    if (existing) {
        // Unlike
        await Like.deleteOne({ _id: existing.id });
        await Post.updateOne({ _id: postId }, { $inc: { likes_count: -1 } });
        res.json({ liked: false });
    } else {
        // Like
        await Like.create({ user_id: userId, post_id: postId });
        await Post.updateOne({ _id: postId }, { $inc: { likes_count: 1 } });
        
        // Create notification
        await Notification.create({
            user_id: post.user_id,
            type: 'like',
            content: `${req.user.name} liked your post`,
            post_id: postId
        });
        
        res.json({ liked: true });
    }
};
```

## Pattern Selection Guide

When analyzing frontend/UI, look for these indicators:

| Frontend Feature | Suggested Pattern |
|------------------|-------------------|
| Data table + forms | CRUD Admin Panel |
| Login page + profile | User Authentication |
| Charts + metrics | Dashboard Analytics |
| Product list + cart | E-commerce |
| Posts + social interactions | Social Features |

Combine multiple patterns as needed for complex applications.
