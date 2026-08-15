const axios = require('axios');

class SMSService {
  constructor() {
    this.baseUrl = process.env.SMS_BASE_URL || 'http://sms.ozonedesk.com/api/v1/send.php';
    this.userId = process.env.SMS_USER_ID || '';
    this.apiKey = process.env.SMS_API_KEY || '';
    this.senderId = process.env.SMS_SENDER_ID || '';
  }

  /**
   * Send SMS notification
   * @param {string} phoneNumber - Phone number (should start with 94)
   * @param {string} message - Message content
   * @returns {Promise<Object>} - API response
   */
  async sendSMS(phoneNumber, message) {
    try {
      // Ensure phone number starts with 94
      let formattedNumber = phoneNumber;
      if (!phoneNumber.startsWith('94')) {
        if (phoneNumber.startsWith('0')) {
          formattedNumber = '94' + phoneNumber.substring(1);
        } else if (phoneNumber.startsWith('+')) {
          formattedNumber = phoneNumber.substring(1);
        } else {
          formattedNumber = '94' + phoneNumber;
        }
      }

      const params = new URLSearchParams({
        user_id: this.userId,
        api_key: this.apiKey,
        sender_id: this.senderId,
        to: formattedNumber,
        message: message
      });

      const response = await axios.get(`${this.baseUrl}?${params.toString()}`);
      
      console.log(`SMS sent to ${formattedNumber}:`, response.data);
      return response.data;
    } catch (error) {
      console.error('SMS sending failed:', error.message);
      throw new Error(`Failed to send SMS: ${error.message}`);
    }
  }

  /**
   * Send booking confirmation SMS
   * @param {Object} booking - Booking object
   * @returns {Promise<Object>} - API response
   */
  async sendBookingConfirmation(booking) {
    const message = `Booking Confirmed! Order: ${booking.orderId}, Slot: ${booking.slotNumber}, Date: ${new Date(booking.date).toLocaleDateString()}, Time: ${booking.startTime}-${booking.endTime}, Vehicle: ${booking.vehicleDetails.make} ${booking.vehicleDetails.model} (${booking.vehicleDetails.licensePlate}). Thank you for choosing our service!`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }

  /**
   * Send booking cancellation SMS
   * @param {Object} booking - Booking object
   * @param {string} reason - Cancellation reason
   * @returns {Promise<Object>} - API response
   */
  async sendBookingCancellation(booking, reason = '') {
    const message = `Booking Cancelled! Order: ${booking.orderId}, Slot: ${booking.slotNumber}, Date: ${new Date(booking.date).toLocaleDateString()}, Time: ${booking.startTime}-${booking.endTime}. ${reason ? `Reason: ${reason}` : ''} For support, contact us.`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }

  /**
   * Send booking completion SMS
   * @param {Object} booking - Booking object
   * @returns {Promise<Object>} - API response
   */
  async sendBookingCompletion(booking) {
    const message = `Booking Completed! Order: ${booking.orderId}, Slot: ${booking.slotNumber}, Date: ${new Date(booking.date).toLocaleDateString()}, Time: ${booking.startTime}-${booking.endTime}. Thank you for using our service! We hope to see you again.`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }

  /**
   * Send unauthorized vehicle alert SMS
   * @param {Object} booking - Booking object
   * @param {string} detectedPlate - Detected license plate
   * @param {string} slotNumber - Slot number
   * @returns {Promise<Object>} - API response
   */
  async sendUnauthorizedVehicleAlert(booking, detectedPlate, slotNumber) {
    const message = `ALERT: Unauthorized vehicle detected! Slot: ${slotNumber}, Detected Plate: ${detectedPlate}, Expected: ${booking.vehicleDetails.licensePlate}, Customer: ${booking.customerDetails.name}. Please check immediately.`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }

  /**
   * Send slot conflict alert SMS
   * @param {Object} booking - Booking object
   * @param {string} conflictingPlate - Conflicting vehicle plate
   * @returns {Promise<Object>} - API response
   */
  async sendSlotConflictAlert(booking, conflictingPlate) {
    const message = `ALERT: Slot conflict detected! Your slot ${booking.slotNumber} has another vehicle (${conflictingPlate}) during your booking time ${booking.startTime}-${booking.endTime}. Please contact support immediately.`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }

  /**
   * Send payment confirmation SMS
   * @param {Object} booking - Booking object
   * @returns {Promise<Object>} - API response
   */
  async sendPaymentConfirmation(booking) {
    const message = `Payment Confirmed! Order: ${booking.orderId}, Amount: LKR ${booking.payment.amount}, Slot: ${booking.slotNumber}, Date: ${new Date(booking.date).toLocaleDateString()}, Time: ${booking.startTime}-${booking.endTime}. Your booking is now active.`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }

  /**
   * Send reminder SMS (for upcoming bookings)
   * @param {Object} booking - Booking object
   * @returns {Promise<Object>} - API response
   */
  async sendBookingReminder(booking) {
    const message = `Reminder: Your booking is tomorrow! Order: ${booking.orderId}, Slot: ${booking.slotNumber}, Date: ${new Date(booking.date).toLocaleDateString()}, Time: ${booking.startTime}-${booking.endTime}, Vehicle: ${booking.vehicleDetails.licensePlate}. Please arrive on time.`;
    
    return this.sendSMS(booking.customerDetails.phone, message);
  }
}

module.exports = new SMSService(); 