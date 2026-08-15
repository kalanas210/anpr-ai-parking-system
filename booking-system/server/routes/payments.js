const express = require('express');
const stripe = require('stripe');
const Booking = require('../models/Booking');
const { protect } = require('../middleware/auth');
const smsService = require('../utils/smsService');

const router = express.Router();

// Initialize Stripe instance function (lazy initialization)
function getStripeInstance() {
  if (!process.env.STRIPE_SECRET_KEY) {
    throw new Error('STRIPE_SECRET_KEY is not set in environment variables');
  }
  return stripe(process.env.STRIPE_SECRET_KEY);
}

// Verify Stripe key is loaded
if (!process.env.STRIPE_SECRET_KEY) {
  console.error('❌ STRIPE_SECRET_KEY is not set in environment variables');
} else {
  console.log('✅ Stripe key available:', process.env.STRIPE_SECRET_KEY.substring(0, 12) + '...');
}

// Test endpoint to debug origin calculation
router.get('/test-origin', (req, res) => {
  console.log('=== ORIGIN DEBUG ===');
  console.log('Origin header:', req.headers.origin);
  console.log('Host header:', req.headers.host);
  console.log('X-Forwarded-Proto:', req.headers['x-forwarded-proto']);
  console.log('Connection encrypted:', req.connection.encrypted);
  
  let origin;
  if (req.headers.origin) {
    origin = req.headers.origin;
  } else if (req.headers.host) {
    const protocol = req.headers['x-forwarded-proto'] || (req.connection.encrypted ? 'https' : 'http');
    origin = `${protocol}://${req.headers.host}`;
  } else {
    origin = 'http://localhost:3000';
  }
  
  origin = origin.replace(/\/$/, '');
  const testUrl = `${origin}/my-bookings?payment_success=true&session_id=test`;
  const finalUrl = testUrl.replace(/([^:])\/+/g, '$1/');
  
  res.json({
    origin: origin,
    testUrl: testUrl,
    finalUrl: finalUrl,
    headers: {
      origin: req.headers.origin,
      host: req.headers.host,
      'x-forwarded-proto': req.headers['x-forwarded-proto']
    }
  });
});

// @desc    Create Stripe checkout session for booking
// @route   POST /api/payments/create-checkout-session
// @access  Private
router.post('/create-checkout-session', protect, async (req, res) => {
  try {
    console.log('Creating checkout session for booking');
    console.log('Request body:', req.body);
    console.log('User:', req.user._id);
    
    const { bookingId, clientOrigin } = req.body;
    
    // Improved origin calculation with debugging
    console.log('All headers:', req.headers);
    console.log('Origin header:', req.headers.origin);
    console.log('Host header:', req.headers.host);
    console.log('X-Forwarded-Proto:', req.headers['x-forwarded-proto']);
    console.log('Connection encrypted:', req.connection.encrypted);
    
    let origin;
    if (clientOrigin) {
      // Prioritize clientOrigin from request body
      origin = clientOrigin;
    } else if (req.headers.origin) {
      origin = req.headers.origin;
    } else if (req.headers.host) {
      const protocol = req.headers['x-forwarded-proto'] || (req.connection.encrypted ? 'https' : 'http');
      origin = `${protocol}://${req.headers.host}`;
    } else {
      origin = 'http://localhost:3000';
    }

    // Ensure origin doesn't end with a slash
    origin = origin.replace(/\/$/, '');
    
    console.log('Final calculated origin:', origin);

    if (!bookingId) {
      console.log('Missing bookingId');
      return res.status(400).json({
        success: false,
        message: 'Booking ID is required'
      });
    }

    console.log('Looking for booking:', bookingId);
    // Verify booking exists and belongs to user
    const booking = await Booking.findById(bookingId);
    if (!booking) {
      console.log('Booking not found');
      return res.status(404).json({
        success: false,
        message: 'Booking not found'
      });
    }

    console.log('Booking found:', booking._id);
    console.log('Booking user:', booking.user.toString());
    console.log('Request user:', req.user._id.toString());

    if (booking.user.toString() !== req.user._id.toString()) {
      console.log('User not authorized for this booking');
      return res.status(403).json({
        success: false,
        message: 'Not authorized to pay for this booking'
      });
    }

    // Check if booking is already paid
    if (booking.payment.status === 'completed') {
      return res.status(400).json({
        success: false,
        message: 'Booking is already paid'
      });
    }

    console.log('Creating Stripe checkout session with amount:', booking.payment.amount);
    
    // Get Stripe instance with lazy initialization
    const stripeInstance = getStripeInstance();
    console.log('- Stripe instance initialized:', !!stripeInstance);
    
    // Create line items for Stripe checkout
    const line_items = [{
      price_data: {
        currency: 'lkr',
        product_data: {
          name: `Parking Booking - Slot ${booking.slotNumber}`,
          description: `Parking slot ${booking.slotNumber} on ${new Date(booking.date).toLocaleDateString()} from ${booking.startTime} to ${booking.endTime}`,
        },
        unit_amount: Math.floor(booking.payment.amount * 100), // Convert to cents
      },
      quantity: 1
    }];

    // Create checkout session
    // Ensure URLs don't have double slashes and are properly formatted
    const successUrl = `${origin}/my-bookings?payment_success=true&session_id={CHECKOUT_SESSION_ID}`;
    const cancelUrl = `${origin}/booking-details/${bookingId}`;
    
    // Final safety check - ensure no double slashes
    const finalSuccessUrl = successUrl.replace(/([^:])\/+/g, '$1/');
    const finalCancelUrl = cancelUrl.replace(/([^:])\/+/g, '$1/');
    

    
    const session = await stripeInstance.checkout.sessions.create({
      line_items,
      mode: 'payment',
      success_url: finalSuccessUrl,
      cancel_url: finalCancelUrl,
      metadata: {
        bookingId: bookingId,
        userId: req.user._id.toString(),
      },
      customer_email: booking.customerDetails.email,
      payment_method_types: ['card'],
    });

    console.log('Checkout session created:', session.id);

    // Update booking with session ID
    booking.payment.stripePaymentIntentId = session.payment_intent;
    booking.payment.stripeSessionId = session.id;
    await booking.save();

    console.log('Booking updated with session ID');

    res.json({
      success: true,
      data: {
        url: session.url,
        sessionId: session.id
      }
    });
  } catch (error) {
    console.error('Create checkout session error:', error);
    console.error('Error stack:', error.stack);
    res.status(500).json({
      success: false,
      message: 'Server error',
      error: process.env.NODE_ENV === 'development' ? error.message : 'Internal server error'
    });
  }
});

// @desc    Stripe webhook
// @route   POST /api/payments/webhook
// @access  Public
router.post('/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
  const sig = req.headers['stripe-signature'];

  let event;

  try {
    const stripeInstance = getStripeInstance();
    event = stripeInstance.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error('Webhook signature verification failed:', err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  // Handle the event
  switch (event.type) {
    case 'checkout.session.completed':
      const session = event.data.object;
      console.log('Checkout session completed!');
      
      try {
        const { bookingId, userId } = session.metadata;
        const booking = await Booking.findById(bookingId);

        if (booking) {
          booking.payment.status = 'completed';
          booking.payment.stripeChargeId = session.payment_intent;
          await booking.save();
          console.log('Booking payment status updated to completed');
          
          // Send payment confirmation SMS
          try {
            await smsService.sendPaymentConfirmation(booking);
            console.log(`Payment confirmation SMS sent for booking ${booking.orderId}`);
          } catch (smsError) {
            console.error('Failed to send payment confirmation SMS:', smsError.message);
          }
        }
      } catch (error) {
        console.error('Error updating booking payment status:', error);
      }
      break;

    case 'payment_intent.succeeded':
      const paymentIntent = event.data.object;
      console.log('PaymentIntent was successful!');
      
      try {
        const booking = await Booking.findOne({
          'payment.stripePaymentIntentId': paymentIntent.id
        });

        if (booking) {
          booking.payment.status = 'completed';
          booking.payment.stripeChargeId = paymentIntent.latest_charge;
          await booking.save();
          console.log('Booking payment status updated to completed');
          
          // Send payment confirmation SMS
          try {
            await smsService.sendPaymentConfirmation(booking);
            console.log(`Payment confirmation SMS sent for booking ${booking.orderId}`);
          } catch (smsError) {
            console.error('Failed to send payment confirmation SMS:', smsError.message);
          }
        }
      } catch (error) {
        console.error('Error updating booking payment status:', error);
      }
      break;

    case 'payment_intent.payment_failed':
      const failedPaymentIntent = event.data.object;
      console.log('PaymentIntent failed!');
      
      try {
        const booking = await Booking.findOne({
          'payment.stripePaymentIntentId': failedPaymentIntent.id
        });

        if (booking) {
          booking.payment.status = 'failed';
          await booking.save();
          console.log('Booking payment status updated to failed');
        }
      } catch (error) {
        console.error('Error updating booking payment status:', error);
      }
      break;

    case 'checkout.session.expired':
      const expiredSession = event.data.object;
      console.log('Checkout session expired!');
      
      try {
        const { bookingId } = expiredSession.metadata;
        const booking = await Booking.findById(bookingId);

        if (booking && booking.payment.status === 'pending') {
          booking.payment.status = 'failed';
          await booking.save();
          console.log('Booking payment status updated to failed due to expired session');
        }
      } catch (error) {
        console.error('Error updating booking payment status:', error);
      }
      break;

    default:
      console.log(`Unhandled event type ${event.type}`);
  }

  res.json({ received: true });
});

// @desc    Get payment status
// @route   GET /api/payments/status/:bookingId
// @access  Private
router.get('/status/:bookingId', protect, async (req, res) => {
  try {
    const booking = await Booking.findById(req.params.bookingId);

    if (!booking) {
      return res.status(404).json({
        success: false,
        message: 'Booking not found'
      });
    }

    if (booking.user.toString() !== req.user._id.toString()) {
      return res.status(403).json({
        success: false,
        message: 'Not authorized to view this payment'
      });
    }

    res.json({
      success: true,
      data: {
        paymentStatus: booking.payment.status,
        amount: booking.payment.amount,
        currency: booking.payment.currency,
        stripePaymentIntentId: booking.payment.stripePaymentIntentId,
        stripeSessionId: booking.payment.stripeSessionId
      }
    });
  } catch (error) {
    console.error('Get payment status error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

// @desc    Verify payment session
// @route   POST /api/payments/verify-session
// @access  Private
router.post('/verify-session', protect, async (req, res) => {
  try {
    const { sessionId } = req.body;

    if (!sessionId) {
      return res.status(400).json({
        success: false,
        message: 'Session ID is required'
      });
    }

    // Retrieve session from Stripe
    const stripeInstance = getStripeInstance();
    const session = await stripeInstance.checkout.sessions.retrieve(sessionId);

    if (session.payment_status === 'paid') {
      // Find booking by session metadata
      const { bookingId } = session.metadata;
      const booking = await Booking.findById(bookingId);

      if (!booking) {
        return res.status(404).json({
          success: false,
          message: 'Booking not found'
        });
      }

      // Update booking payment status if not already updated
      if (booking.payment.status !== 'completed') {
        booking.payment.status = 'completed';
        booking.payment.stripeChargeId = session.payment_intent;
        await booking.save();
      }

      res.json({
        success: true,
        data: {
          booking: booking,
          paymentStatus: 'completed',
          session: session
        },
        message: 'Payment verified successfully'
      });
    } else {
      res.status(400).json({
        success: false,
        message: 'Payment not completed',
        paymentStatus: session.payment_status
      });
    }
  } catch (error) {
    console.error('Verify session error:', error);
    res.status(500).json({
      success: false,
      message: 'Server error'
    });
  }
});

module.exports = router;