const mongoose = require('mongoose');

const slotStatusSchema = new mongoose.Schema({
  slotNumber: {
    type: Number,
    required: [true, 'Slot number is required'],
    enum: [1, 2] // Only 2 slots for now
  },
  status: {
    type: String,
    required: [true, 'Status is required'],
    enum: ['free', 'busy', 'unknown'],
    default: 'unknown'
  },
  timestamp: {
    type: Date,
    default: Date.now
  },
  updatedBy: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: false // Can be null if updated by detection system
  },
  source: {
    type: String,
    enum: ['detection_system', 'manual', 'booking_system'],
    default: 'detection_system'
  },
  metadata: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  }
}, {
  timestamps: true
});

// Index for efficient queries
slotStatusSchema.index({ slotNumber: 1, timestamp: -1 });
slotStatusSchema.index({ status: 1, timestamp: -1 });

// Get latest status for a slot
slotStatusSchema.statics.getLatestStatus = function(slotNumber) {
  return this.findOne({ slotNumber })
    .sort({ timestamp: -1 })
    .limit(1);
};

// Get status history for a slot
slotStatusSchema.statics.getStatusHistory = function(slotNumber, startDate, endDate, limit = 100) {
  const query = { slotNumber };
  
  if (startDate && endDate) {
    query.timestamp = {
      $gte: new Date(startDate),
      $lte: new Date(endDate)
    };
  }
  
  return this.find(query)
    .sort({ timestamp: -1 })
    .limit(limit);
};

// Get current status for all slots
slotStatusSchema.statics.getCurrentStatus = function() {
  return this.aggregate([
    {
      $group: {
        _id: '$slotNumber',
        latestStatus: { $first: '$$ROOT' }
      }
    },
    {
      $sort: { 'latestStatus.timestamp': -1 }
    }
  ]);
};

module.exports = mongoose.model('SlotStatus', slotStatusSchema); 