import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useBooking } from '../contexts/BookingContext';
import LoadingSpinner from '../components/LoadingSpinner';

const BookingDetails = () => {
  const { id } = useParams();
  const { getBookingById, cancelBooking, currentBooking, loading } = useBooking();
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    if (id) {
      getBookingById(id);
    }
  }, [id]);

  const handleCancelBooking = async () => {
    if (window.confirm('Are you sure you want to cancel this booking?')) {
      setIsCancelling(true);
      try {
        await cancelBooking(id);
      } finally {
        setIsCancelling(false);
      }
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      confirmed: { class: 'badge-success', text: 'Confirmed' },
      completed: { class: 'badge-info', text: 'Completed' },
      cancelled: { class: 'badge-danger', text: 'Cancelled' },
      no_show: { class: 'badge-warning', text: 'No Show' }
    };

    const config = statusConfig[status] || { class: 'badge-info', text: status };
    return <span className={`badge ${config.class}`}>{config.text}</span>;
  };

  const getPaymentStatusBadge = (paymentStatus) => {
    const statusConfig = {
      completed: { class: 'badge-success', text: 'Paid' },
      pending: { class: 'badge-warning', text: 'Pending' },
      failed: { class: 'badge-danger', text: 'Failed' },
      refunded: { class: 'badge-info', text: 'Refunded' }
    };

    const config = statusConfig[paymentStatus] || { class: 'badge-info', text: paymentStatus };
    return <span className={`badge ${config.class}`}>{config.text}</span>;
  };

  if (loading && !currentBooking) {
    return <LoadingSpinner text="Loading booking details..." />;
  }

  if (!currentBooking) {
    return (
      <div style={{ padding: '2rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center' }}>
            <h1>Booking Not Found</h1>
            <p>The booking you're looking for doesn't exist or you don't have permission to view it.</p>
            <Link to="/my-bookings" className="btn btn-primary">
              Back to My Bookings
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem 0' }}>
      <div className="container">
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          {/* Header */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '2rem'
          }}>
            <h1 style={{ fontSize: '2rem', fontWeight: '700', color: '#1f2937' }}>
              Booking Details
            </h1>
            <Link to="/my-bookings" className="btn btn-outline">
              Back to Bookings
            </Link>
          </div>

          {/* Booking Status */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '1rem'
            }}>
              <h2 style={{ margin: 0, color: '#1f2937' }}>
                {currentBooking.slotNumber}
              </h2>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {getStatusBadge(currentBooking.status)}
                {getPaymentStatusBadge(currentBooking.payment.status)}
              </div>
            </div>
            <p style={{ margin: 0, color: '#6b7280' }}>
              Booking ID: {currentBooking._id}
            </p>
            {currentBooking.orderId && (
              <p style={{ margin: '0.5rem 0 0 0', color: '#3b82f6', fontWeight: '500' }}>
                Order ID: {currentBooking.orderId}
              </p>
            )}
          </div>

          {/* Booking Information */}
          <div className="grid grid-cols-2" style={{ gap: '2rem', marginBottom: '2rem' }}>
            {/* Date and Time */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Date & Time</h3>
              </div>
              <div>
                <p><strong>Date:</strong> {new Date(currentBooking.date).toLocaleDateString()}</p>
                <p><strong>Start Time:</strong> {currentBooking.startTime}</p>
                <p><strong>End Time:</strong> {currentBooking.endTime}</p>
                <p><strong>Duration:</strong> {
                  Math.ceil((new Date(`2000-01-01T${currentBooking.endTime}`) - new Date(`2000-01-01T${currentBooking.startTime}`)) / (1000 * 60 * 60))
                } hours</p>
              </div>
            </div>

            {/* Payment Information */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Payment Details</h3>
              </div>
              <div>
                <p><strong>Amount:</strong> ${currentBooking.payment.amount}</p>
                <p><strong>Currency:</strong> {currentBooking.payment.currency}</p>
                <p><strong>Status:</strong> {getPaymentStatusBadge(currentBooking.payment.status)}</p>
                {currentBooking.payment.stripeChargeId && (
                  <p><strong>Transaction ID:</strong> {currentBooking.payment.stripeChargeId}</p>
                )}
              </div>
            </div>
          </div>

          {/* Vehicle Information */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div className="card-header">
              <h3 className="card-title">Vehicle Information</h3>
            </div>
            <div className="grid grid-cols-2" style={{ gap: '1rem' }}>
              <div>
                <p><strong>Make:</strong> {currentBooking.vehicleDetails.make}</p>
                <p><strong>Model:</strong> {currentBooking.vehicleDetails.model}</p>
              </div>
              <div>
                <p><strong>Color:</strong> {currentBooking.vehicleDetails.color}</p>
                <p><strong>License Plate:</strong> {currentBooking.vehicleDetails.licensePlate}</p>
              </div>
            </div>
          </div>

          {/* Customer Information */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div className="card-header">
              <h3 className="card-title">Customer Information</h3>
            </div>
            <div className="grid grid-cols-2" style={{ gap: '1rem' }}>
              <div>
                <p><strong>Name:</strong> {currentBooking.customerDetails.name}</p>
                <p><strong>Email:</strong> {currentBooking.customerDetails.email}</p>
              </div>
              <div>
                <p><strong>Phone:</strong> {currentBooking.customerDetails.phone}</p>
                <p><strong>Booking Type:</strong> {currentBooking.isPreBooked ? 'Pre-booked' : 'Walk-in'}</p>
              </div>
            </div>
          </div>

          {/* Additional Information */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div className="card-header">
              <h3 className="card-title">Additional Information</h3>
            </div>
            <div>
              <p><strong>Created:</strong> {new Date(currentBooking.createdAt).toLocaleString()}</p>
              <p><strong>Last Updated:</strong> {new Date(currentBooking.updatedAt).toLocaleString()}</p>
              {currentBooking.actualArrivalTime && (
                <p><strong>Actual Arrival:</strong> {new Date(currentBooking.actualArrivalTime).toLocaleString()}</p>
              )}
              {currentBooking.actualDepartureTime && (
                <p><strong>Actual Departure:</strong> {new Date(currentBooking.actualDepartureTime).toLocaleString()}</p>
              )}
              {currentBooking.notes && (
                <p><strong>Notes:</strong> {currentBooking.notes}</p>
              )}
            </div>
          </div>

          {/* Actions */}
          {currentBooking.status === 'confirmed' && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Actions</h3>
              </div>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <button
                  onClick={handleCancelBooking}
                  className="btn btn-danger"
                  disabled={isCancelling}
                >
                  {isCancelling ? (
                    <>
                      <div className="loading" style={{ marginRight: '0.5rem' }}></div>
                      Cancelling...
                    </>
                  ) : (
                    'Cancel Booking'
                  )}
                </button>
                <Link to="/my-bookings" className="btn btn-outline">
                  Back to Bookings
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BookingDetails; 