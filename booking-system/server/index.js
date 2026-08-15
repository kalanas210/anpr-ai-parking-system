// Load environment variables FIRST - before any other imports
const dotenv = require('dotenv');
dotenv.config();

// Now import other modules after env vars are loaded
const express = require('express');
const cors = require('cors');
const connectDB = require('./config/database');
const authRoutes = require('./routes/auth');
const bookingRoutes = require('./routes/bookings');
const paymentRoutes = require('./routes/payments');
const adminRoutes = require('./routes/admin');
const slotRoutes = require('./routes/slots');
const parkingIntegrationRoutes = require('./routes/parking-integration');

// Debug: Check if environment variables are loaded
console.log('Environment check:');
console.log('MONGODB_URI:', process.env.MONGODB_URI ? 'SET' : 'NOT SET');
console.log('JWT_SECRET:', process.env.JWT_SECRET ? 'SET' : 'NOT SET');
console.log('STRIPE_PUBLISH_KEY:', process.env.STRIPE_PUBLISH_KEY ? 'SET' : 'NOT SET');
console.log('STRIPE_SECRET_KEY:', process.env.STRIPE_SECRET_KEY ? 'SET' : 'NOT SET');
console.log('PORT:', process.env.PORT || 'DEFAULT (5000)');
console.log('NODE_ENV:', process.env.NODE_ENV || 'development');

// Fail fast if required secrets are missing. They MUST be provided via .env
// (copy booking-system/server/.env.example to .env). No secrets are hard-coded.
const requiredEnv = ['MONGODB_URI', 'JWT_SECRET', 'STRIPE_SECRET_KEY'];
const missingEnv = requiredEnv.filter((key) => !process.env[key]);
if (missingEnv.length > 0) {
  console.error(`❌ Missing required environment variables: ${missingEnv.join(', ')}`);
  console.error('   Copy booking-system/server/.env.example to .env and fill in your values.');
  process.exit(1);
}

const app = express();

// Connect to MongoDB
connectDB();

// Middleware
// Restrict CORS to known origins (comma-separated ALLOWED_ORIGINS in .env);
// defaults to the local React dev server.
const allowedOrigins = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000')
  .split(',')
  .map((o) => o.trim());
app.use(cors({ origin: allowedOrigins, credentials: true }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/bookings', bookingRoutes);
app.use('/api/payments', paymentRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/slots', slotRoutes);
app.use('/api/parking', parkingIntegrationRoutes);

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'OK', 
    message: 'Server is running',
    environment: {
      nodeEnv: process.env.NODE_ENV,
      port: process.env.PORT,
      mongoUri: process.env.MONGODB_URI ? 'SET' : 'NOT SET',
      stripeKey: process.env.STRIPE_SECRET_KEY ? 'SET' : 'NOT SET'
    }
  });
});

// Test auth endpoint
app.get('/api/test-auth', (req, res) => {
  res.json({ 
    message: 'Auth test endpoint',
    headers: {
      authorization: req.headers.authorization ? 'PRESENT' : 'MISSING'
    }
  });
});

// Test Stripe endpoint
app.get('/api/test-stripe', async (req, res) => {
  try {
    const stripe = require('stripe');
    const stripeInstance = stripe(process.env.STRIPE_SECRET_KEY);
    
    // Test Stripe connection by creating a simple payment intent
    const paymentIntent = await stripeInstance.paymentIntents.create({
      amount: 1000, // $10.00
              currency: 'lkr',
      metadata: { test: 'true' }
    });
    
    res.json({
      success: true,
      message: 'Stripe connection successful',
      paymentIntentId: paymentIntent.id,
      stripeKey: process.env.STRIPE_SECRET_KEY ? 'SET' : 'NOT SET',
      stripeKeyLength: process.env.STRIPE_SECRET_KEY ? process.env.STRIPE_SECRET_KEY.length : 0
    });
  } catch (error) {
    console.error('Stripe test error:', error);
    res.status(500).json({
      success: false,
      message: 'Stripe connection failed',
      error: error.message,
      stripeKey: process.env.STRIPE_SECRET_KEY ? 'SET' : 'NOT SET'
    });
  }
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ 
    success: false, 
    message: 'Something went wrong!',
    error: process.env.NODE_ENV === 'development' ? err.message : {}
  });
});

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});