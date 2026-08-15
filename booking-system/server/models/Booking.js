const mongoose = require('mongoose');

const bookingSchema = new mongoose.Schema({
  orderId: {
    type: String,
    unique: true,
    required: false
  },
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  slotNumber: {
    type: String,
    required: [true, 'Slot number is required'],
    trim: true
  },
  date: {
    type: Date,
    required: [true, 'Date is required']
  },
  startTime: {
    type: String,
    required: [true, 'Start time is required']
  },
  endTime: {
    type: String,
    required: [true, 'End time is required']
  },
  vehicleDetails: {
    make: {
      type: String,
      required: [true, 'Vehicle make is required'],
      trim: true
    },
    model: {
      type: String,
      required: [true, 'Vehicle model is required'],
      trim: true
    },
    color: {
      type: String,
      required: [true, 'Vehicle color is required'],
      trim: true
    },
    licensePlate: {
      type: String,
      required: [true, 'License plate is required'],
      trim: true,
      uppercase: true
    }
  },
  customerDetails: {
    name: {
      type: String,
      required: [true, 'Customer name is required'],
      trim: true
    },
    phone: {
      type: String,
      required: [true, 'Phone number is required'],
      trim: true
    },
    email: {
      type: String,
      required: [true, 'Email is required'],
      trim: true,
      lowercase: true
    }
  },
  payment: {
    amount: {
      type: Number,
      required: [true, 'Payment amount is required']
    },
    currency: {
      type: String,
      default: 'LKR'
    },
    status: {
      type: String,
      enum: ['pending', 'completed', 'failed', 'refunded'],
      default: 'pending'
    },
    stripePaymentIntentId: {
      type: String,
      trim: true
    },
    stripeSessionId: {
      type: String,
      trim: true
    },
    stripeChargeId: {
      type: String,
      trim: true
    }
  },
  status: {
    type: String,
    enum: ['confirmed', 'cancelled', 'completed', 'no_show'],
    default: 'confirmed'
  },
  isPreBooked: {
    type: Boolean,
    default: true
  },
  actualArrivalTime: {
    type: Date
  },
  actualDepartureTime: {
    type: Date
  },
  notes: {
    type: String,
    trim: true
  },
  cancellationReason: {
    type: String,
    trim: true
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  updatedAt: {
    type: Date,
    default: Date.now
  }
}, {
  timestamps: true
});

// Generate order ID before saving
bookingSchema.pre('save', async function(next) {
  if (this.isNew) {
    const date = new Date();
    const year = date.getFullYear().toString().slice(-2);
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const random = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    this.orderId = `ORD${year}${month}${day}${random}`;
  }
  next();
});

// Index for efficient queries
bookingSchema.index({ slotNumber: 1, date: 1, startTime: 1, endTime: 1 });
bookingSchema.index({ user: 1, createdAt: -1 });
bookingSchema.index({ status: 1, date: 1 });
bookingSchema.index({ orderId: 1 });

module.exports = mongoose.model('Booking', bookingSchema); 