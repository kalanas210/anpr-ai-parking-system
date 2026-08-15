const Booking = require('../models/Booking');
const SlotStatus = require('../models/SlotStatus');
const cron = require('node-cron');

class AutoCompletionService {
  constructor() {
    this.isRunning = false;
  }

  // Start the automatic completion service
  start() {
    if (this.isRunning) {
      console.log('Auto-completion service is already running');
      return;
    }

    console.log('Starting auto-completion service...');

    // Run every minute to check for expired bookings
    cron.schedule('* * * * *', async () => {
      await this.processExpiredBookings();
    }, {
      scheduled: true,
      timezone: "Asia/Colombo"
    });

    // Run every 5 minutes to update slot status
    cron.schedule('*/5 * * * *', async () => {
      await this.updateSlotStatus();
    }, {
      scheduled: true,
      timezone: "Asia/Colombo"
    });

    this.isRunning = true;
    console.log('Auto-completion service started successfully');
  }

  // Stop the automatic completion service
  stop() {
    if (!this.isRunning) {
      console.log('Auto-completion service is not running');
      return;
    }

    cron.getTasks().forEach(task => task.stop());
    this.isRunning = false;
    console.log('Auto-completion service stopped');
  }

  // Process expired bookings and mark them as completed
  async processExpiredBookings() {
    try {
      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5); // HH:MM format
      const currentDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

      // Find bookings that have ended but are still confirmed
      const expiredBookings = await Booking.find({
        date: { $lte: currentDate },
        endTime: { $lt: currentTime },
        status: 'confirmed',
        'payment.status': 'completed' // Only complete paid bookings
      });

      console.log(`Found ${expiredBookings.length} expired bookings to process`);

      for (const booking of expiredBookings) {
        try {
          // Mark booking as completed
          booking.status = 'completed';
          booking.actualDepartureTime = new Date();
          booking.notes = booking.notes ? 
            `${booking.notes}\nAuto-completed at ${new Date().toISOString()}` : 
            `Auto-completed at ${new Date().toISOString()}`;
          
          await booking.save();
          
          console.log(`✅ Auto-completed booking ${booking.orderId} (Slot ${booking.slotNumber})`);
          
          // Update slot status to free
          await this.updateSlotStatusForBooking(booking.slotNumber, 'free');
          
        } catch (error) {
          console.error(`❌ Error auto-completing booking ${booking.orderId}:`, error);
        }
      }

      // Also handle no-show bookings (bookings that never arrived)
      await this.processNoShowBookings();

    } catch (error) {
      console.error('Error in processExpiredBookings:', error);
    }
  }

  // Process no-show bookings
  async processNoShowBookings() {
    try {
      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5);
      const currentDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

      // Find confirmed bookings that ended without arrival
      const noShowBookings = await Booking.find({
        date: { $lt: currentDate }, // Past dates
        endTime: { $lt: currentTime },
        status: 'confirmed',
        'payment.status': 'completed',
        actualArrivalTime: { $exists: false } // Never arrived
      });

      console.log(`Found ${noShowBookings.length} no-show bookings to process`);

      for (const booking of noShowBookings) {
        try {
          booking.status = 'no_show';
          booking.notes = booking.notes ? 
            `${booking.notes}\nMarked as no-show at ${new Date().toISOString()}` : 
            `Marked as no-show at ${new Date().toISOString()}`;
          
          await booking.save();
          
          console.log(`⚠️ Marked booking ${booking.orderId} as no-show (Slot ${booking.slotNumber})`);
          
          // Update slot status to free
          await this.updateSlotStatusForBooking(booking.slotNumber, 'free');
          
        } catch (error) {
          console.error(`❌ Error processing no-show booking ${booking.orderId}:`, error);
        }
      }

    } catch (error) {
      console.error('Error in processNoShowBookings:', error);
    }
  }

  // Update slot status based on current bookings
  async updateSlotStatus() {
    try {
      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5);
      const currentDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());

      // Get all slots
      const slots = [1, 2];

      for (const slotNumber of slots) {
        try {
          // Check if there's an active booking for this slot
          const activeBooking = await Booking.findOne({
            slotNumber: slotNumber.toString(),
            date: currentDate,
            status: { $in: ['confirmed', 'completed'] },
            startTime: { $lte: currentTime },
            endTime: { $gt: currentTime }
          });

          let newStatus = 'free';
          let metadata = {};

          if (activeBooking) {
            newStatus = 'busy';
            metadata = {
              bookingId: activeBooking._id,
              orderId: activeBooking.orderId,
              customerName: activeBooking.customerDetails.name,
              licensePlate: activeBooking.vehicleDetails.licensePlate,
              startTime: activeBooking.startTime,
              endTime: activeBooking.endTime,
              status: activeBooking.status
            };
          }

          // Update slot status
          await this.updateSlotStatusForBooking(slotNumber, newStatus, metadata);

        } catch (error) {
          console.error(`❌ Error updating slot ${slotNumber} status:`, error);
        }
      }

    } catch (error) {
      console.error('Error in updateSlotStatus:', error);
    }
  }

  // Update status for a specific slot
  async updateSlotStatusForBooking(slotNumber, status, metadata = {}) {
    try {
      const slotStatus = new SlotStatus({
        slotNumber: parseInt(slotNumber),
        status,
        source: 'booking_system',
        metadata: {
          ...metadata,
          updatedAt: new Date().toISOString(),
          reason: 'automatic_update'
        }
      });

      await slotStatus.save();
      
      console.log(`🔄 Updated slot ${slotNumber} status to: ${status}`);
      
    } catch (error) {
      console.error(`❌ Error updating slot ${slotNumber} status:`, error);
    }
  }

  // Manual trigger for testing
  async manualTrigger() {
    console.log('Manual trigger for auto-completion service');
    await this.processExpiredBookings();
    await this.updateSlotStatus();
  }

  // Get service status
  getStatus() {
    return {
      isRunning: this.isRunning,
      lastCheck: new Date().toISOString()
    };
  }
}

// Create singleton instance
const autoCompletionService = new AutoCompletionService();

module.exports = autoCompletionService; 