import React, { useState } from 'react';
import { toast } from 'react-toastify';

const PaymentForm = ({ booking, onSuccess }) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  const handlePayment = async () => {
    setIsProcessing(true);
    setError(null);

    try {
      console.log('Client origin:', window.location.origin);
      console.log('Client href:', window.location.href);
      console.log('Booking ID:', booking._id);
      
      // Create checkout session
      const response = await fetch('/api/payments/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Origin': window.location.origin
        },
        body: JSON.stringify({
          bookingId: booking._id,
          clientOrigin: window.location.origin
        })
      });

      console.log('Response status:', response.status);
      console.log('Response headers:', Object.fromEntries(response.headers.entries()));

      const result = await response.json();
      console.log('API Response:', result);
      
      if (result.success) {
        console.log('Redirecting to Stripe URL:', result.data.url);
        // Redirect to Stripe Checkout
        window.location.href = result.data.url;
      } else {
        console.error('API Error:', result);
        setError(result.message || 'Failed to create payment session');
        toast.error(result.message || 'Failed to create payment session');
      }
    } catch (error) {
      console.error('Payment error:', error);
      setError('Payment processing failed');
      toast.error('Payment processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div>
      {/* Enhanced Booking Summary */}
      <div className="card" style={{
        background: 'linear-gradient(135deg, var(--gray-50) 0%, white 100%)',
        border: '2px solid var(--gray-100)',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '4px',
          background: 'var(--gradient-primary)'
        }}></div>
        
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--spacing-md)',
          marginBottom: 'var(--spacing-lg)'
        }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'var(--gradient-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontSize: '1.5rem',
            fontWeight: 'bold',
            boxShadow: 'var(--shadow-md)'
          }}>
            📋
          </div>
          <div>
            <h4 style={{ 
              margin: 0, 
              color: 'var(--uom-primary)', 
              fontSize: '1.5rem',
              fontWeight: '700'
            }}>
              Booking Summary
            </h4>
            <p style={{
              margin: 'var(--spacing-xs) 0 0 0',
              color: 'var(--gray-500)',
              fontSize: '0.875rem'
            }}>
              Review your booking details before payment
            </p>
          </div>
        </div>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: 'var(--spacing-lg)',
          fontSize: '1rem'
        }}>
          <div style={{
            background: 'white',
            padding: 'var(--spacing-lg)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--gray-100)',
            boxShadow: 'var(--shadow-sm)'
          }}>
            <h5 style={{
              margin: '0 0 var(--spacing-md) 0',
              color: 'var(--uom-primary)',
              fontSize: '1rem',
              fontWeight: '600',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              📍 Location Details
            </h5>
            <div style={{ display: 'grid', gap: 'var(--spacing-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--gray-600)', fontWeight: '500' }}>Slot:</span>
                <span style={{ fontWeight: '600', color: 'var(--gray-900)' }}>{booking.slotNumber}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--gray-600)', fontWeight: '500' }}>Date:</span>
                <span style={{ fontWeight: '600', color: 'var(--gray-900)' }}>
                  {new Date(booking.date).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--gray-600)', fontWeight: '500' }}>Time:</span>
                <span style={{ fontWeight: '600', color: 'var(--gray-900)' }}>
                  {booking.startTime} - {booking.endTime}
                </span>
              </div>
            </div>
          </div>

          <div style={{
            background: 'white',
            padding: 'var(--spacing-lg)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--gray-100)',
            boxShadow: 'var(--shadow-sm)'
          }}>
            <h5 style={{
              margin: '0 0 var(--spacing-md) 0',
              color: 'var(--uom-primary)',
              fontSize: '1rem',
              fontWeight: '600',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              🚗 Vehicle Details
            </h5>
            <div style={{ display: 'grid', gap: 'var(--spacing-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--gray-600)', fontWeight: '500' }}>Vehicle:</span>
                <span style={{ fontWeight: '600', color: 'var(--gray-900)' }}>
                  {booking.vehicleDetails.make} {booking.vehicleDetails.model}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--gray-600)', fontWeight: '500' }}>Color:</span>
                <span style={{ fontWeight: '600', color: 'var(--gray-900)' }}>
                  {booking.vehicleDetails.color}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--gray-600)', fontWeight: '500' }}>License:</span>
                <span style={{ 
                  fontWeight: '600', 
                  color: 'var(--gray-900)',
                  fontFamily: 'monospace',
                  fontSize: '1.1rem',
                  letterSpacing: '0.1em'
                }}>
                  {booking.vehicleDetails.licensePlate}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Total Amount Section */}
        <div style={{
          marginTop: 'var(--spacing-lg)',
          padding: 'var(--spacing-lg)',
          background: 'var(--gradient-primary)',
          borderRadius: 'var(--radius-lg)',
          color: 'white',
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent)',
            animation: 'shimmer 3s infinite'
          }}></div>
          
          <div style={{ position: 'relative', zIndex: 1 }}>
            <p style={{
              margin: '0 0 var(--spacing-sm) 0',
              fontSize: '1rem',
              opacity: 0.9,
              color: 'white'
            }}>
              Total Amount
            </p>
            <h3 style={{
              margin: 0,
              fontSize: '2.5rem',
              fontWeight: '900',
              textShadow: '2px 2px 4px rgba(0,0,0,0.3)',
              color: 'white'
            }}>
              LKR {booking.payment.amount}
            </h3>
            <p style={{
              margin: 'var(--spacing-sm) 0 0 0',
              fontSize: '0.875rem',
              opacity: 0.8,
              color: 'white'
            }}>
              Secure payment via Stripe
            </p>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div style={{
          backgroundColor: 'var(--error-50)',
          color: 'var(--error-700)',
          padding: 'var(--spacing-lg)',
          borderRadius: 'var(--radius-lg)',
          marginBottom: 'var(--spacing-lg)',
          fontSize: '0.875rem',
          border: '1px solid var(--error-200)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--spacing-sm)'
        }}>
          <span style={{ fontSize: '1.25rem' }}>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Enhanced Payment Button */}
      <button
        onClick={handlePayment}
        className="btn btn-gold"
        style={{ 
          width: '100%',
          padding: 'var(--spacing-lg)',
          fontSize: '1.25rem',
          fontWeight: '700',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg)',
          cursor: isProcessing ? 'not-allowed' : 'pointer',
          opacity: isProcessing ? 0.7 : 1,
          position: 'relative',
          overflow: 'hidden'
        }}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <>
            <div style={{
              display: 'inline-block',
              width: '24px',
              height: '24px',
              border: '3px solid rgba(255,255,255,0.3)',
              borderRadius: '50%',
              borderTopColor: 'white',
              animation: 'spin 1s ease-in-out infinite',
              marginRight: 'var(--spacing-sm)'
            }}></div>
            Processing Payment...
          </>
        ) : (
          <>
            <span style={{ marginRight: 'var(--spacing-sm)' }}>💳</span>
            Pay LKR {booking.payment.amount}
          </>
        )}
      </button>

      {/* Enhanced Security Notice */}
      <div style={{
        marginTop: 'var(--spacing-lg)',
        padding: 'var(--spacing-lg)',
        backgroundColor: 'var(--success-50)',
        borderRadius: 'var(--radius-lg)',
        fontSize: '0.875rem',
        color: 'var(--success-700)',
        border: '1px solid var(--success-200)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--spacing-md)'
      }}>
        <div style={{
          width: '24px',
          height: '24px',
          borderRadius: '50%',
          background: 'var(--success-500)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '0.75rem',
          fontWeight: 'bold',
          flexShrink: 0
        }}>
          🔒
        </div>
        <div>
          <p style={{ 
            margin: '0 0 var(--spacing-sm) 0', 
            fontWeight: '600',
            fontSize: '1rem'
          }}>
            Secure Payment via Stripe
          </p>
          <p style={{ margin: '0 0 var(--spacing-sm) 0' }}>
            You'll be redirected to Stripe's secure payment page to complete your transaction.
            All payments are encrypted and protected.
          </p>
          <div style={{
            background: 'white',
            padding: 'var(--spacing-sm) var(--spacing-md)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--success-200)',
            fontSize: '0.75rem',
            fontFamily: 'monospace'
          }}>
            <strong>Test Card:</strong> 4242 4242 4242 4242 | <strong>Expiry:</strong> Any future date | <strong>CVC:</strong> Any 3 digits
          </div>
        </div>
      </div>

      {/* CSS for shimmer animation */}
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default PaymentForm; 