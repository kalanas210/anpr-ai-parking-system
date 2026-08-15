const express = require('express');
const { body, validationResult } = require('express-validator');
const Booking = require('../models/Booking');
const { protect } = require('../middleware/auth');
const smsService = require('../utils/smsService');

const router = express.Router();

// @desc    Get available slots for a date
// @route   GET /api/bookings/available-slots
// @access  Public
router.get('/available-slots', async (req, res) => {
  try {
    const { date, startTime, endTime } = req.query;

    if (!date || !startTime || !endTime) {
      return res.status(400).json({
        success: false,
        message: 'Date, start time, and end time are required'
      });
    }

    const queryDate = new Date(date);
    queryDate.setHours(0, 0, 0, 0);

    // Get all slots (only 2 slots: 1 and 2)
    const allSlots = ['Slot 1', 'Slot 2'];

    // Get booked slots for the specified date and time
    const bookedSlots = await Booking.find({
      date: queryDate,
      status: { $in: ['confirmed', 'completed'] },
      $or: [
        {
          startTime: { $lt: endTime },
          endTime: { $gt: startTime }
        }
      ]
    }).select('slotNumber');

    const bookedSlotNumbers = bookedSlots.map(booking => booking.slotNumber);
    let availableSlots = allSlots.filter(slot => !bookedSlotNumbers.includes(slot));

    // Check if booking is for today and get real-time status
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const isBookingForToday = queryDate.getTime() === today.getTime();

    if (isBookingForToday) {
      try {
        // Get real-time status from main parking system
        const axios = require('axios');
        const possibleUrls = [
          'http://127.0.0.1:5000/api/parking-status',
          'http://localhost:5000/api/parking-status',
          'http://127.0.0.1:5001/api/parking-status',
          'http://localhost:5001/api/parking-status'
        ];

        let realtimeStatus = null;
        for (const url of possibleUrls) {
          try {
            const response = await axios.get(url, { timeout: 3000 });
            if (response.data && response.status === 200) {
              realtimeStatus = response.data;
              break;
            }
          } catch (error) {
            console.log(`Failed to connect to ${url}: ${error.message}`);
          }
        }

        // If we got real-time status, filter out busy slots
        if (realtimeStatus) {
          const busySlots = [];
          
          // Check slot 1
          if (realtimeStatus['1'] && realtimeStatus['1'].occupied) {
            busySlots.push('Slot 1');
          }
          
          // Check slot 2
          if (realtimeStatus['2'] && realtimeStatus['2'].occupied) {
            busySlots.push('Slot 2');
          }

          // Remove busy slots from available slots for today
          availableSlots = availableSlots.filter(slot => !busySlots.includes(slot));
          
          console.log(`Real-time status check: Busy slots for today: ${busySlots.join(', ')}`);
        }
      } catch (error) {
        console.log('Could not get real-time status, proceeding with booking system data only');
      }
    }

    res.json({
      success: true,
      data: {
        date: date,
        startTime: startTime,
        endTime: endTime,
        availableSlots: availableSlots,
        totalSlots: allSlots.length,
        bookedSlots: bookedSlotNumbers.length,
        isToday: isBookingForToday,
        realtimeCheck: isBookingForToday
      }
    });
  } catch (error) {
    console.error('Get available slots error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Create a new booking
// @route   POST /api/bookings
// @access  Private
router.post('/', protect, [
  body('slotNumber').trim().notEmpty().withMessage('Slot number is required'),
  body('date').isISO8601().withMessage('Valid date is required'),
  body('startTime').trim().notEmpty().withMessage('Start time is required'),
  body('endTime').trim().notEmpty().withMessage('End time is required'),
  body('vehicleDetails.make').trim().notEmpty().withMessage('Vehicle make is required'),
  body('vehicleDetails.model').trim().notEmpty().withMessage('Vehicle model is required'),
  body('vehicleDetails.color').trim().notEmpty().withMessage('Vehicle color is required'),
  body('vehicleDetails.licensePlate').trim().notEmpty().withMessage('License plate is required'),
  body('customerDetails.name').trim().notEmpty().withMessage('Customer name is required'),
  body('customerDetails.phone').trim().notEmpty().withMessage('Phone number is required'),
  body('customerDetails.email').isEmail().normalizeEmail().withMessage('Valid email is required'),
  body('payment.amount').isNumeric().withMessage('Valid payment amount is required')
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        success: false,
        message: 'Validation errors',
        errors: errors.array()
      });
    }

    const {
      slotNumber,
      date,
      startTime,
      endTime,
      vehicleDetails,
      customerDetails,
      payment
    } = req.body;

    // Check if slot is available for the specified time
    const queryDate = new Date(date);
    queryDate.setHours(0, 0, 0, 0);

    const conflictingBooking = await Booking.findOne({
      slotNumber,
      date: queryDate,
      status: { $in: ['confirmed', 'completed'] },
      $or: [
        {
          startTime: { $lt: endTime },
          endTime: { $gt: startTime }
        }
      ]
    });

    if (conflictingBooking) {
      return res.status(400).json({
        success: false,
        message: 'Selected slot is not available for the specified time'
      });
    }

    // Check if booking is for today and verify real-time status
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const isBookingForToday = queryDate.getTime() === today.getTime();

    if (isBookingForToday) {
      try {
        // Get real-time status from main parking system
        const axios = require('axios');
        const possibleUrls = [
          'http://127.0.0.1:5000/api/parking-status',
          'http://localhost:5000/api/parking-status',
          'http://127.0.0.1:5001/api/parking-status',
          'http://localhost:5001/api/parking-status'
        ];

        let realtimeStatus = null;
        for (const url of possibleUrls) {
          try {
            const response = await axios.get(url, { timeout: 3000 });
            if (response.data && response.status === 200) {
              realtimeStatus = response.data;
              break;
            }
          } catch (error) {
            console.log(`Failed to connect to ${url}: ${error.message}`);
          }
        }

        // If we got real-time status, check if the slot is busy
        if (realtimeStatus) {
          const slotNum = slotNumber.replace('Slot ', '');
          const slotStatus = realtimeStatus[slotNum];
          
          if (slotStatus && slotStatus.occupied) {
            return res.status(400).json({
              success: false,
              message: `Slot ${slotNumber} is currently occupied by a vehicle (${slotStatus.license_plate || 'Unknown'}). Cannot book this slot for today as we don't know when the vehicle will leave. Please choose a different slot or date.`
            });
          }
        }
      } catch (error) {
        console.log('Could not verify real-time status, proceeding with booking');
      }
    }

    // Create booking
    const booking = await Booking.create({
      user: req.user._id,
      slotNumber,
      date: queryDate,
      startTime,
      endTime,
      vehicleDetails,
      customerDetails,
      payment
    });

    // Send booking confirmation SMS
    try {
      await smsService.sendBookingConfirmation(booking);
      console.log(`SMS confirmation sent for booking ${booking.orderId}`);
    } catch (smsError) {
      console.error('Failed to send booking confirmation SMS:', smsError.message);
      // Don't fail the booking creation if SMS fails
    }

    res.status(201).json({
      success: true,
      data: booking
    });
  } catch (error) {
    console.error('Create booking error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Get user's bookings
// @route   GET /api/bookings/my-bookings
// @access  Private
router.get('/my-bookings', protect, async (req, res) => {
  try {
    const { page = 1, limit = 10, status } = req.query;
    const skip = (page - 1) * limit;

    let query = { user: req.user._id };
    if (status) {
      query.status = status;
    }

    const bookings = await Booking.find(query)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(parseInt(limit))
      .populate('user', 'name email phone');

    const total = await Booking.countDocuments(query);

    res.json({
      success: true,
      data: {
        bookings,
        pagination: {
          currentPage: parseInt(page),
          totalPages: Math.ceil(total / limit),
          totalBookings: total,
          hasNextPage: skip + bookings.length < total,
          hasPrevPage: page > 1
        }
      }
    });
  } catch (error) {
    console.error('Get my bookings error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Get active bookings for today (for parking system integration)
// @route   GET /api/bookings/active
// @access  Public (for parking system)
router.get('/active', async (req, res) => {
  try {
    const { date } = req.query;
    const queryDate = date ? new Date(date) : new Date();
    queryDate.setHours(0, 0, 0, 0);

    // Auto-cancel expired bookings
    const currentTime = new Date().toTimeString().slice(0, 5); // HH:MM format
    const expiredBookings = await Booking.find({
      date: queryDate,
      status: 'confirmed',
      endTime: { $lt: currentTime }
    });

    // Cancel expired bookings
    for (const booking of expiredBookings) {
      booking.status = 'cancelled';
      booking.cancellationReason = 'Auto-cancelled: Time expired';
      await booking.save();
      console.log(`Auto-cancelled booking ${booking._id}: Time expired`);
    }

    const activeBookings = await Booking.find({
      date: queryDate,
      status: { $in: ['confirmed', 'completed'] }
    }).populate('user', 'name email phone');

    res.json({
      success: true,
      data: activeBookings,
      autoCancelled: expiredBookings.length
    });
  } catch (error) {
    console.error('Get active bookings error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Get booking by ID
// @route   GET /api/bookings/:id
// @access  Private
router.get('/:id', protect, async (req, res) => {
  try {
    const booking = await Booking.findById(req.params.id)
      .populate('user', 'name email phone');

    if (!booking) {
      return res.status(404).json({
        success: false,
        message: 'Booking not found'
      });
    }

    // Check if user owns this booking or is admin
    if (booking.user._id.toString() !== req.user._id.toString() && req.user.role !== 'admin') {
      return res.status(403).json({
        success: false,
        message: 'Not authorized to view this booking'
      });
    }

    res.json({
      success: true,
      data: booking
    });
  } catch (error) {
    console.error('Get booking error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Cancel booking
// @route   PUT /api/bookings/:id/cancel
// @access  Private
router.put('/:id/cancel', protect, async (req, res) => {
  try {
    const booking = await Booking.findById(req.params.id);

    if (!booking) {
      return res.status(404).json({
        success: false,
        message: 'Booking not found'
      });
    }

    // Check if user owns this booking
    if (booking.user.toString() !== req.user._id.toString()) {
      return res.status(403).json({
        success: false,
        message: 'Not authorized to cancel this booking'
      });
    }

    // Check if booking can be cancelled (not completed or already cancelled)
    if (booking.status === 'completed' || booking.status === 'cancelled') {
      return res.status(400).json({
        success: false,
        message: 'Booking cannot be cancelled'
      });
    }

    booking.status = 'cancelled';
    await booking.save();

    // Send booking cancellation SMS
    try {
      await smsService.sendBookingCancellation(booking, req.body.reason || '');
      console.log(`SMS cancellation sent for booking ${booking.orderId}`);
    } catch (smsError) {
      console.error('Failed to send booking cancellation SMS:', smsError.message);
      // Don't fail the cancellation if SMS fails
    }

    res.json({
      success: true,
      data: booking,
      message: 'Booking cancelled successfully'
    });
  } catch (error) {
    console.error('Cancel booking error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

module.exports = router; 