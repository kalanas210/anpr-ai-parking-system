const express = require('express');
const Booking = require('../models/Booking');
const smsService = require('../utils/smsService');

const router = express.Router();

// @desc    Report unauthorized vehicle in slot
// @route   POST /api/parking/unauthorized-vehicle
// @access  Public (for parking system)
router.post('/unauthorized-vehicle', async (req, res) => {
  try {
    const { slotNumber, detectedPlate, timestamp } = req.body;

    if (!slotNumber || !detectedPlate) {
      return res.status(400).json({
        success: false,
        message: 'Slot number and detected plate are required'
      });
    }

    // Find the booking for this slot at the current time
    const currentDate = new Date();
    currentDate.setHours(0, 0, 0, 0);
    const currentTime = new Date().toTimeString().slice(0, 5); // HH:MM format

    const booking = await Booking.findOne({
      slotNumber,
      date: currentDate,
      status: { $in: ['confirmed', 'completed'] },
      startTime: { $lte: currentTime },
      endTime: { $gte: currentTime }
    });

    if (!booking) {
      return res.status(404).json({
        success: false,
        message: 'No active booking found for this slot'
      });
    }

    // Check if the detected plate matches the expected plate
    if (detectedPlate.toUpperCase() === booking.vehicleDetails.licensePlate.toUpperCase()) {
      return res.json({
        success: true,
        message: 'Vehicle plate matches booking',
        data: {
          bookingId: booking._id,
          expectedPlate: booking.vehicleDetails.licensePlate,
          detectedPlate: detectedPlate,
          customerName: booking.customerDetails.name
        }
      });
    }

    // Send unauthorized vehicle alert SMS
    try {
      await smsService.sendUnauthorizedVehicleAlert(booking, detectedPlate, slotNumber);
      console.log(`Unauthorized vehicle alert SMS sent for booking ${booking.orderId}`);
    } catch (smsError) {
      console.error('Failed to send unauthorized vehicle alert SMS:', smsError.message);
    }

    res.json({
      success: true,
      message: 'Unauthorized vehicle detected and alert sent',
      data: {
        bookingId: booking._id,
        expectedPlate: booking.vehicleDetails.licensePlate,
        detectedPlate: detectedPlate,
        customerName: booking.customerDetails.name,
        customerPhone: booking.customerDetails.phone
      }
    });
  } catch (error) {
    console.error('Unauthorized vehicle detection error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Report slot conflict (multiple vehicles in same slot)
// @route   POST /api/parking/slot-conflict
// @access  Public (for parking system)
router.post('/slot-conflict', async (req, res) => {
  try {
    const { slotNumber, detectedPlates, timestamp } = req.body;

    if (!slotNumber || !detectedPlates || !Array.isArray(detectedPlates)) {
      return res.status(400).json({
        success: false,
        message: 'Slot number and detected plates array are required'
      });
    }

    // Find all bookings for this slot at the current time
    const currentDate = new Date();
    currentDate.setHours(0, 0, 0, 0);
    const currentTime = new Date().toTimeString().slice(0, 5); // HH:MM format

    const bookings = await Booking.find({
      slotNumber,
      date: currentDate,
      status: { $in: ['confirmed', 'completed'] },
      startTime: { $lte: currentTime },
      endTime: { $gte: currentTime }
    });

    if (bookings.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'No active bookings found for this slot'
      });
    }

    const alerts = [];

    // Send slot conflict alerts to all affected customers
    for (const booking of bookings) {
      const conflictingPlates = detectedPlates.filter(plate => 
        plate.toUpperCase() !== booking.vehicleDetails.licensePlate.toUpperCase()
      );

      if (conflictingPlates.length > 0) {
        try {
          await smsService.sendSlotConflictAlert(booking, conflictingPlates.join(', '));
          console.log(`Slot conflict alert SMS sent for booking ${booking.orderId}`);
          
          alerts.push({
            bookingId: booking._id,
            customerName: booking.customerDetails.name,
            customerPhone: booking.customerDetails.phone,
            expectedPlate: booking.vehicleDetails.licensePlate,
            conflictingPlates: conflictingPlates
          });
        } catch (smsError) {
          console.error('Failed to send slot conflict alert SMS:', smsError.message);
        }
      }
    }

    res.json({
      success: true,
      message: 'Slot conflict detected and alerts sent',
      data: {
        slotNumber,
        detectedPlates,
        alerts
      }
    });
  } catch (error) {
    console.error('Slot conflict detection error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Get current slot status for parking system
// @route   GET /api/parking/slot-status
// @access  Public (for parking system)
router.get('/slot-status', async (req, res) => {
  try {
    const { date } = req.query;
    const queryDate = date ? new Date(date) : new Date();
    queryDate.setHours(0, 0, 0, 0);
    const currentTime = new Date().toTimeString().slice(0, 5); // HH:MM format

    const activeBookings = await Booking.find({
      date: queryDate,
      status: { $in: ['confirmed', 'completed'] },
      startTime: { $lte: currentTime },
      endTime: { $gte: currentTime }
    }).select('slotNumber vehicleDetails customerDetails startTime endTime orderId');

    const slotStatus = {
      'Slot 1': null,
      'Slot 2': null
    };

    activeBookings.forEach(booking => {
      // Ensure slot number is properly formatted
      const slotNumber = booking.slotNumber.toString().replace('Slot ', '');
      const slotKey = `Slot ${slotNumber}`;
      slotStatus[slotKey] = {
        bookingId: booking._id,
        orderId: booking.orderId,
        expectedPlate: booking.vehicleDetails.licensePlate,
        customerName: booking.customerDetails.name,
        vehicleModel: booking.vehicleDetails.model,
        vehicleMake: booking.vehicleDetails.make,
        ownerName: booking.customerDetails.name,
        startTime: booking.startTime,
        endTime: booking.endTime
      };
    });

    res.json({
      success: true,
      data: {
        date: queryDate.toISOString().split('T')[0],
        currentTime,
        slotStatus
      }
    });
  } catch (error) {
    console.error('Get slot status error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Get real-time slot status from main parking system
// @route   GET /api/parking/realtime-status
// @access  Public
router.get('/realtime-status', async (req, res) => {
  try {
    // Try to connect to the main parking system (app.py or app_video.py)
    const axios = require('axios');
    
    // Try different possible URLs for the main parking system
    const possibleUrls = [
      'http://127.0.0.1:5000/api/parking-status',
      'http://localhost:5000/api/parking-status',
      'http://127.0.0.1:5001/api/parking-status',
      'http://localhost:5001/api/parking-status'
    ];

    let parkingStatus = null;
    let connectedUrl = null;

    for (const url of possibleUrls) {
      try {
        const response = await axios.get(url, { timeout: 3000 });
        if (response.data && response.status === 200) {
          parkingStatus = response.data;
          connectedUrl = url;
          break;
        }
      } catch (error) {
        console.log(`Failed to connect to ${url}:`, error.message);
        continue;
      }
    }

    if (!parkingStatus) {
      return res.status(503).json({
        success: false,
        message: 'Main parking system is not running. Please start app.py or app_video.py first.',
        data: {
          slot1: { status: 'unknown', message: 'System offline' },
          slot2: { status: 'unknown', message: 'System offline' }
        }
      });
    }

    // Transform the parking status to match our expected format
    const slotStatus = {
      slot1: {
        status: 'unknown',
        lastUpdated: new Date().toISOString(),
        message: 'No data'
      },
      slot2: {
        status: 'unknown',
        lastUpdated: new Date().toISOString(),
        message: 'No data'
      }
    };

    // Process the parking status data
    if (parkingStatus['1']) {
      const slot1Data = parkingStatus['1'];
      slotStatus.slot1 = {
        status: slot1Data.occupied ? 'busy' : 'free',
        lastUpdated: new Date().toISOString(),
        licensePlate: slot1Data.license_plate || 'Unknown',
        vehicleType: slot1Data.vehicle_type || 'Unknown',
        entryTime: slot1Data.entry_time,
        parkingDuration: slot1Data.parking_duration,
        message: slot1Data.occupied ? 'Vehicle detected' : 'Slot available'
      };
    }

    if (parkingStatus['2']) {
      const slot2Data = parkingStatus['2'];
      slotStatus.slot2 = {
        status: slot2Data.occupied ? 'busy' : 'free',
        lastUpdated: new Date().toISOString(),
        licensePlate: slot2Data.license_plate || 'Unknown',
        vehicleType: slot2Data.vehicle_type || 'Unknown',
        entryTime: slot2Data.entry_time,
        parkingDuration: slot2Data.parking_duration,
        message: slot2Data.occupied ? 'Vehicle detected' : 'Slot available'
      };
    }

    res.json({
      success: true,
      data: slotStatus,
      source: 'main_parking_system',
      connectedUrl: connectedUrl,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Get real-time slot status error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to get real-time slot status',
      error: error.message
    });
  }
});

// @desc    Send booking reminder SMS (for scheduled reminders)
// @route   POST /api/parking/send-reminder
// @access  Private (admin only)
router.post('/send-reminder', async (req, res) => {
  try {
    const { bookingId } = req.body;

    if (!bookingId) {
      return res.status(400).json({
        success: false,
        message: 'Booking ID is required'
      });
    }

    const booking = await Booking.findById(bookingId);
    if (!booking) {
      return res.status(404).json({
        success: false,
        message: 'Booking not found'
      });
    }

    // Send reminder SMS
    try {
      await smsService.sendBookingReminder(booking);
      console.log(`Reminder SMS sent for booking ${booking.orderId}`);
    } catch (smsError) {
      console.error('Failed to send reminder SMS:', smsError.message);
      return res.status(500).json({
        success: false,
        message: 'Failed to send reminder SMS'
      });
    }

    res.json({
      success: true,
      message: 'Reminder SMS sent successfully',
      data: {
        bookingId: booking._id,
        orderId: booking.orderId,
        customerName: booking.customerDetails.name,
        customerPhone: booking.customerDetails.phone
      }
    });
  } catch (error) {
    console.error('Send reminder error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

module.exports = router; 