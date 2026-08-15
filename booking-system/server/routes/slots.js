const express = require('express');
const Booking = require('../models/Booking');
const SlotStatus = require('../models/SlotStatus');
const { protect } = require('../middleware/auth');

const router = express.Router();

// @desc    Get slot status
// @route   GET /api/slots/status
// @access  Public
router.get('/status', async (req, res) => {
  try {
    const { date, startTime, endTime } = req.query;
    
    // If date and time are provided, check booking conflicts
    if (date && startTime && endTime) {
      const queryDate = new Date(date);
      queryDate.setHours(0, 0, 0, 0);

      // Get bookings for the specified time
      const bookings = await Booking.find({
        date: queryDate,
        status: { $in: ['confirmed', 'completed'] },
        $or: [
          {
            startTime: { $lt: endTime },
            endTime: { $gt: startTime }
          }
        ]
      });

      // Determine slot status based on bookings
      const slotStatus = {
        slot1: { status: 'free', lastUpdated: new Date().toISOString() },
        slot2: { status: 'free', lastUpdated: new Date().toISOString() }
      };

      bookings.forEach(booking => {
        const slotKey = `slot${booking.slotNumber}`;
        slotStatus[slotKey] = {
          status: 'busy',
          lastUpdated: new Date().toISOString(),
          booking: {
            id: booking._id,
            orderId: booking.orderId,
            customerName: booking.customerDetails.name,
            licensePlate: booking.vehicleDetails.licensePlate,
            startTime: booking.startTime,
            endTime: booking.endTime,
            status: booking.status
          }
        };
      });

      return res.json({
        success: true,
        data: slotStatus
      });
    }

    // If no specific time provided, get current real-time status
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5);
    const currentDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    // Get current active bookings
    const activeBookings = await Booking.find({
      date: currentDate,
      status: { $in: ['confirmed', 'completed'] },
      startTime: { $lte: currentTime },
      endTime: { $gt: currentTime }
    });

    // Get latest slot status from detection system
    const latestSlotStatus = await SlotStatus.aggregate([
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

    // Combine booking data with detection system data
    const slotStatus = {
      slot1: { status: 'unknown', lastUpdated: new Date().toISOString() },
      slot2: { status: 'unknown', lastUpdated: new Date().toISOString() }
    };

    // Update with detection system data
    latestSlotStatus.forEach(slot => {
      const slotKey = `slot${slot._id}`;
      slotStatus[slotKey] = {
        status: slot.latestStatus.status,
        lastUpdated: slot.latestStatus.timestamp.toISOString(),
        source: slot.latestStatus.source
      };
    });

    // Override with booking data if there's an active booking
    activeBookings.forEach(booking => {
      const slotKey = `slot${booking.slotNumber}`;
      slotStatus[slotKey] = {
        status: 'busy',
        lastUpdated: new Date().toISOString(),
        source: 'booking_system',
        booking: {
          id: booking._id,
          orderId: booking.orderId,
          customerName: booking.customerDetails.name,
          licensePlate: booking.vehicleDetails.licensePlate,
          startTime: booking.startTime,
          endTime: booking.endTime,
          status: booking.status
        }
      };
    });

    res.json({
      success: true,
      data: slotStatus,
      currentTime: currentTime,
      currentDate: currentDate.toISOString().split('T')[0]
    });

  } catch (error) {
    console.error('Get slot status error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Update slot status (for detection system integration)
// @route   POST /api/slots/status
// @access  Public (for detection system)
router.post('/status', async (req, res) => {
  try {
    const { slotNumber, status, source = 'detection_system', metadata = {} } = req.body;

    if (!slotNumber || !status) {
      return res.status(400).json({
        success: false,
        message: 'Slot number and status are required'
      });
    }

    // Validate slot number
    if (![1, 2].includes(parseInt(slotNumber))) {
      return res.status(400).json({
        success: false,
        message: 'Invalid slot number. Must be 1 or 2.'
      });
    }

    // Validate status
    if (!['free', 'busy', 'unknown'].includes(status)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid status. Must be free, busy, or unknown.'
      });
    }

    // Create new slot status entry
    const slotStatus = new SlotStatus({
      slotNumber: parseInt(slotNumber),
      status,
      source,
      metadata: {
        ...metadata,
        updatedAt: new Date().toISOString()
      }
    });

    await slotStatus.save();

    console.log(`Slot ${slotNumber} status updated to: ${status} (source: ${source})`);

    res.json({
      success: true,
      data: slotStatus,
      message: 'Slot status updated successfully'
    });

  } catch (error) {
    console.error('Update slot status error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Get slot status history
// @route   GET /api/slots/history/:slotNumber
// @access  Public
router.get('/history/:slotNumber', async (req, res) => {
  try {
    const { slotNumber } = req.params;
    const { startDate, endDate, limit = 100 } = req.query;

    if (![1, 2].includes(parseInt(slotNumber))) {
      return res.status(400).json({
        success: false,
        message: 'Invalid slot number. Must be 1 or 2.'
      });
    }

    const history = await SlotStatus.getStatusHistory(
      parseInt(slotNumber),
      startDate,
      endDate,
      parseInt(limit)
    );

    res.json({
      success: true,
      data: history
    });

  } catch (error) {
    console.error('Get slot history error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

module.exports = router; 