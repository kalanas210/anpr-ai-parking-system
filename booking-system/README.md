# Smart Parking Booking System

A comprehensive parking booking system with automatic order completion and real-time slot status management.

## Features

### 🚗 Core Booking System
- **User Registration & Authentication**: Secure user accounts with JWT tokens
- **Slot Booking**: Book parking slots with date and time selection
- **Payment Integration**: Stripe payment processing
- **Booking Management**: View, cancel, and manage bookings
- **Admin Dashboard**: Comprehensive admin interface

### 🤖 Automatic Order Completion
- **Auto-Completion Service**: Automatically marks expired bookings as completed
- **No-Show Detection**: Identifies and marks bookings where customers never arrived
- **Real-time Slot Status**: Updates slot availability based on current bookings
- **Scheduled Tasks**: Runs every minute to process expired bookings
- **Manual Controls**: Admin can start/stop service and trigger manual processing

### 📊 Real-time Slot Management
- **Detection System Integration**: Receives real-time updates from parking sensors
- **Booking System Override**: Booking system takes precedence over detection data
- **Status History**: Tracks all slot status changes with timestamps
- **Conflict Resolution**: Handles conflicts between detection and booking data

## System Architecture

### Backend (Node.js + Express + MongoDB)
```
booking-system/server/
├── models/
│   ├── Booking.js          # Booking data model
│   ├── User.js             # User data model
│   └── SlotStatus.js       # Slot status tracking
├── routes/
│   ├── auth.js             # Authentication endpoints
│   ├── bookings.js         # Booking management
│   ├── payments.js         # Stripe payment processing
│   ├── admin.js            # Admin operations
│   └── slots.js            # Slot status management
├── utils/
│   └── autoCompletion.js   # Auto-completion service
└── index.js                # Main server file
```

### Frontend (React)
```
booking-system/client/
├── src/
│   ├── components/         # Reusable UI components
│   ├── pages/             # Page components
│   ├── contexts/          # React contexts
│   └── App.js             # Main app component
```

## Auto-Completion Service

The auto-completion service runs automatically and handles:

### 🕐 Scheduled Tasks
- **Every Minute**: Checks for expired bookings and marks them as completed
- **Every 5 Minutes**: Updates slot status based on current bookings

### 📋 Processing Logic
1. **Expired Bookings**: Finds confirmed bookings that have passed their end time
2. **Payment Verification**: Only completes bookings with successful payments
3. **No-Show Detection**: Identifies bookings where customers never arrived
4. **Slot Status Update**: Updates slot availability after booking completion

### 🎛️ Admin Controls
- **Service Status**: View if auto-completion service is running
- **Manual Trigger**: Manually run the completion process
- **Start/Stop**: Control the service operation
- **Real-time Monitoring**: Track service activity

## API Endpoints

### Auto-Completion Service
```
GET    /api/admin/auto-completion/status     # Get service status
POST   /api/admin/auto-completion/start      # Start service
POST   /api/admin/auto-completion/stop       # Stop service
POST   /api/admin/auto-completion/trigger    # Manual trigger
```

### Slot Management
```
GET    /api/slots/status                     # Get current slot status
POST   /api/slots/status                     # Update slot status
GET    /api/slots/history/:slotNumber        # Get slot history
```

### Booking Management
```
GET    /api/bookings/active                  # Get active bookings
POST   /api/bookings/:id/arrival             # Update arrival time
POST   /api/bookings/:id/departure           # Update departure time
```

## Installation & Setup

### Prerequisites
- Node.js (v14 or higher)
- MongoDB
- Stripe account (for payments)

### Backend Setup
```bash
cd booking-system/server
npm install
npm run dev
```

### Frontend Setup
```bash
cd booking-system/client
npm install
npm start
```

### Environment Variables
Create `.env` files in both server and client directories:

**Server (.env)**
```env
MONGODB_URI=your_mongodb_connection_string
JWT_SECRET=your_jwt_secret
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
PORT=5000
```

**Client (.env)**
```env
REACT_APP_API_URL=http://localhost:5000/api
REACT_APP_STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
```

## Usage

### For Users
1. **Register/Login**: Create an account or sign in
2. **Book a Slot**: Select date, time, and vehicle details
3. **Make Payment**: Complete payment via Stripe
4. **Track Booking**: Monitor booking status and arrival/departure

### For Admins
1. **Dashboard Access**: View system statistics and recent bookings
2. **Auto-Completion Control**: Monitor and control the auto-completion service
3. **Booking Management**: Manage all bookings and user accounts
4. **System Monitoring**: Track slot status and system health

### For Detection System Integration
1. **Slot Status Updates**: POST to `/api/slots/status` with detection data
2. **Real-time Integration**: System automatically combines detection and booking data
3. **Conflict Resolution**: Booking system takes precedence over detection data

## Technical Details

### Auto-Completion Logic
```javascript
// Example: Processing expired bookings
const expiredBookings = await Booking.find({
  date: { $lte: currentDate },
  endTime: { $lt: currentTime },
  status: 'confirmed',
  'payment.status': 'completed'
});

// Mark as completed
booking.status = 'completed';
booking.actualDepartureTime = new Date();
await booking.save();
```

### Slot Status Management
```javascript
// Example: Updating slot status
const slotStatus = new SlotStatus({
  slotNumber: parseInt(slotNumber),
  status: 'busy', // or 'free'
  source: 'booking_system',
  metadata: { bookingId, customerName, etc. }
});
await slotStatus.save();
```

## Monitoring & Logging

The system provides comprehensive logging:
- **Auto-completion activities**: Tracks all automatic booking completions
- **Slot status changes**: Logs all slot status updates
- **Error handling**: Detailed error logs for debugging
- **Admin dashboard**: Real-time service status monitoring

## Security Features

- **JWT Authentication**: Secure user sessions
- **Role-based Access**: Admin and user permissions
- **Payment Security**: Stripe integration with webhook verification
- **Input Validation**: Comprehensive request validation
- **Error Handling**: Secure error responses

## Future Enhancements

- **Email Notifications**: Automated booking reminders
- **Mobile App**: Native mobile application
- **Analytics Dashboard**: Advanced reporting and analytics
- **Multi-location Support**: Support for multiple parking locations
- **IoT Integration**: Direct sensor integration

## Support

For technical support or questions, please refer to the documentation or contact the development team. 