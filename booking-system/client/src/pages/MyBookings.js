import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useBooking } from '../contexts/BookingContext';
import LoadingSpinner from '../components/LoadingSpinner';

const MyBookings = () => {
  const [currentPage, setCurrentPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [pagination, setPagination] = useState(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [searchParams] = useSearchParams();
  
  const { userBookings, getUserBookings, cancelBooking, loading } = useBooking();

  useEffect(() => {
    loadBookings();
    
    // Check for payment success redirect
    const paymentSuccess = searchParams.get('payment_success');
    const sessionId = searchParams.get('session_id');
    
    if (paymentSuccess === 'true' && sessionId) {
      setShowSuccessMessage(true);
      // Auto-hide success message after 5 seconds
      setTimeout(() => setShowSuccessMessage(false), 5000);
    }
  }, [currentPage, statusFilter, searchParams]);

  const loadBookings = async () => {
    const result = await getUserBookings(currentPage, 10, statusFilter || null);
    if (result) {
      setPagination(result.pagination);
    }
  };

  const handleCancelBooking = async (bookingId) => {
    if (window.confirm('Are you sure you want to cancel this booking?')) {
      await cancelBooking(bookingId);
      loadBookings();
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      confirmed: { class: 'badge-success', text: 'Confirmed', icon: '✅' },
      completed: { class: 'badge-info', text: 'Completed', icon: '🏁' },
      cancelled: { class: 'badge-danger', text: 'Cancelled', icon: '❌' },
      no_show: { class: 'badge-warning', text: 'No Show', icon: '⚠️' }
    };

    const config = statusConfig[status] || { class: 'badge-info', text: status, icon: '📋' };
    return (
      <span className={`badge ${config.class}`} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
        <span>{config.icon}</span>
        {config.text}
      </span>
    );
  };

  const getPaymentStatusBadge = (paymentStatus) => {
    const statusConfig = {
      completed: { class: 'badge-success', text: 'Paid', icon: '💳' },
      pending: { class: 'badge-warning', text: 'Pending', icon: '⏳' },
      failed: { class: 'badge-danger', text: 'Failed', icon: '❌' },
      refunded: { class: 'badge-info', text: 'Refunded', icon: '↩️' }
    };

    const config = statusConfig[paymentStatus] || { class: 'badge-info', text: paymentStatus, icon: '💰' };
    return (
      <span className={`badge ${config.class}`} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
        <span>{config.icon}</span>
        {config.text}
      </span>
    );
  };

  if (loading && !userBookings.length) {
    return <LoadingSpinner text="Loading your bookings..." />;
  }

  return (
    <div style={{ padding: '2rem 0' }}>
      <div className="container">
        <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '2rem'
          }}>
            <h1 style={{ fontSize: '2rem', fontWeight: '700', color: '#1f2937' }}>
              My Bookings
            </h1>
            <Link to="/book" className="btn btn-primary">
              New Booking
            </Link>
          </div>

          {/* Payment Success Message */}
          {showSuccessMessage && (
            <div className="card" style={{ 
              backgroundColor: '#d1fae5', 
              border: '1px solid #10b981',
              marginBottom: '2rem'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '1rem',
                color: '#065f46'
              }}>
                <div style={{ fontSize: '1.5rem' }}>✅</div>
                <div>
                  <h4 style={{ margin: '0 0 0.5rem 0', color: '#065f46' }}>
                    Payment Successful!
                  </h4>
                  <p style={{ margin: 0, fontSize: '0.875rem' }}>
                    Your booking has been confirmed and payment processed successfully. 
                    You can view your booking details below.
                  </p>
                </div>
                <button
                  onClick={() => setShowSuccessMessage(false)}
                  style={{
                    marginLeft: 'auto',
                    background: 'none',
                    border: 'none',
                    fontSize: '1.25rem',
                    cursor: 'pointer',
                    color: '#065f46'
                  }}
                >
                  ×
                </button>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <label className="form-label">Filter by Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="form-input"
                  style={{ width: 'auto', minWidth: '150px' }}
                >
                  <option value="">All Statuses</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="no_show">No Show</option>
                </select>
              </div>
              
              <div style={{ marginLeft: 'auto' }}>
                <p style={{ margin: 0, color: '#6b7280', fontSize: '0.875rem' }}>
                  Total: {pagination?.totalBookings || 0} bookings
                </p>
              </div>
            </div>
          </div>

          {/* Bookings List */}
          {userBookings.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🚗</div>
              <h3 style={{ marginBottom: '1rem', color: '#6b7280' }}>No bookings found</h3>
              <p style={{ color: '#6b7280', marginBottom: '2rem' }}>
                {statusFilter ? 'No bookings match your current filter.' : 'You haven\'t made any bookings yet.'}
              </p>
              <Link to="/book" className="btn btn-primary">
                Make Your First Booking
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1" style={{ gap: '1rem' }}>
              {userBookings.map((booking) => (
                <div key={booking._id} className="card" style={{
                  transition: 'all 0.3s ease',
                  cursor: 'pointer',
                  border: '1px solid #e5e7eb'
                }} onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 10px 25px rgba(0, 0, 0, 0.1)';
                }} onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.1)';
                }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                    gap: '1rem'
                  }}>
                    <div style={{ flex: 1, minWidth: '250px' }}>
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center',
                        marginBottom: '1rem'
                      }}>
                        <div>
                          <h3 style={{ margin: 0, color: '#1f2937' }}>
                            {booking.slotNumber}
                          </h3>
                          {booking.orderId && (
                            <p style={{ 
                              margin: '0.25rem 0 0 0', 
                              color: '#3b82f6', 
                              fontSize: '0.875rem',
                              fontWeight: '500'
                            }}>
                              Order ID: {booking.orderId}
                            </p>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {getStatusBadge(booking.status)}
                          {getPaymentStatusBadge(booking.payment.status)}
                        </div>
                      </div>

                      <div className="grid grid-cols-2" style={{ gap: '1rem', marginBottom: '1rem' }}>
                        <div>
                          <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                            <strong>Date:</strong> {new Date(booking.date).toLocaleDateString()}
                          </p>
                          <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                            <strong>Time:</strong> {booking.startTime} - {booking.endTime}
                          </p>
                          <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                            <strong>Vehicle:</strong> {booking.vehicleDetails.make} {booking.vehicleDetails.model}
                          </p>
                        </div>
                        <div>
                          <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                            <strong>Color:</strong> {booking.vehicleDetails.color}
                          </p>
                          <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                            <strong>License:</strong> {booking.vehicleDetails.licensePlate}
                          </p>
                          <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                            <strong>Amount:</strong> LKR {booking.payment.amount}
                          </p>
                        </div>
                      </div>

                      <p style={{ 
                        margin: '0.25rem 0', 
                        color: '#6b7280', 
                        fontSize: '0.875rem',
                        fontStyle: 'italic'
                      }}>
                        Booked on {new Date(booking.createdAt).toLocaleString()}
                      </p>
                    </div>

                    <div style={{ 
                      display: 'flex', 
                      flexDirection: 'column', 
                      gap: '0.5rem',
                      minWidth: '120px'
                    }}>
                      <Link 
                        to={`/booking/${booking._id}`}
                        className="btn btn-outline"
                        style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                      >
                        View Details
                      </Link>
                      
                      {booking.status === 'confirmed' && (
                        <button
                          onClick={() => handleCancelBooking(booking._id)}
                          className="btn btn-danger"
                          style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {pagination && pagination.totalPages > 1 && (
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center',
              gap: '1rem',
              marginTop: '2rem'
            }}>
              <button
                onClick={() => setCurrentPage(currentPage - 1)}
                className="btn btn-outline"
                disabled={!pagination.hasPrevPage}
              >
                Previous
              </button>
              
              <span style={{ color: '#6b7280' }}>
                Page {pagination.currentPage} of {pagination.totalPages}
              </span>
              
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                className="btn btn-outline"
                disabled={!pagination.hasNextPage}
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MyBookings; 