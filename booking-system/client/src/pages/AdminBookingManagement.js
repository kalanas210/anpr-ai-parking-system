import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';
import LoadingSpinner from '../components/LoadingSpinner';
import AdminCalendar from '../components/AdminCalendar';

const AdminBookingManagement = () => {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedBookings, setSelectedBookings] = useState([]);
  const [selectAll, setSelectAll] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalBookings, setTotalBookings] = useState(0);
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'calendar'
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  
  // Filters
  const [filters, setFilters] = useState({
    status: '',
    date: '',
    slotNumber: '',
    customerName: '',
    paymentStatus: ''
  });

  useEffect(() => {
    loadBookings();
  }, [currentPage, filters]);

  const loadBookings = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage,
        limit: 20,
        ...filters
      });

      console.log('AdminBookingManagement: Loading bookings with params:', Object.fromEntries(params.entries()));
      const response = await axios.get(`/api/admin/bookings?${params}`);
      const { bookings, pagination } = response.data.data;
      
      console.log('AdminBookingManagement: Received bookings:', bookings.length);
      setBookings(bookings);
      setTotalPages(pagination.totalPages);
      setTotalBookings(pagination.totalBookings);
    } catch (error) {
      console.error('Error loading bookings:', error);
      toast.error('Failed to load bookings');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    console.log('AdminBookingManagement: Filter changed:', key, '=', value);
    setFilters(prev => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  };

  const handleDateSelect = (date) => {
    console.log('AdminBookingManagement: Date selected:', date);
    setSelectedDate(date);
    handleFilterChange('date', date);
  };

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedBookings([]);
      setSelectAll(false);
    } else {
      setSelectedBookings(bookings.map(b => b._id));
      setSelectAll(true);
    }
  };

  const handleSelectBooking = (bookingId) => {
    setSelectedBookings(prev => {
      if (prev.includes(bookingId)) {
        return prev.filter(id => id !== bookingId);
      } else {
        return [...prev, bookingId];
      }
    });
  };

  const handleBulkAction = async (action) => {
    if (selectedBookings.length === 0) {
      toast.warning('Please select bookings first');
      return;
    }

    try {
      switch (action) {
        case 'delete':
          if (window.confirm(`Are you sure you want to delete ${selectedBookings.length} booking(s)?`)) {
            await Promise.all(selectedBookings.map(id => 
              axios.delete(`/api/admin/bookings/${id}`)
            ));
            toast.success(`${selectedBookings.length} booking(s) deleted successfully`);
          }
          break;
        case 'confirm':
          await Promise.all(selectedBookings.map(id => 
            axios.put(`/api/admin/bookings/${id}/status`, { status: 'confirmed' })
          ));
          toast.success(`${selectedBookings.length} booking(s) confirmed successfully`);
          break;
        case 'complete':
          await Promise.all(selectedBookings.map(id => 
            axios.put(`/api/admin/bookings/${id}/status`, { status: 'completed' })
          ));
          toast.success(`${selectedBookings.length} booking(s) completed successfully`);
          break;
        case 'cancel':
          await Promise.all(selectedBookings.map(id => 
            axios.put(`/api/admin/bookings/${id}/status`, { status: 'cancelled' })
          ));
          toast.success(`${selectedBookings.length} booking(s) cancelled successfully`);
          break;
      }
      setSelectedBookings([]);
      setSelectAll(false);
      loadBookings();
    } catch (error) {
      console.error('Bulk action error:', error);
      toast.error('Failed to perform bulk action');
    }
  };

  const handleDeleteBooking = async (bookingId) => {
    if (window.confirm('Are you sure you want to delete this booking?')) {
      try {
        await axios.delete(`/api/admin/bookings/${bookingId}`);
        toast.success('Booking deleted successfully');
        loadBookings();
      } catch (error) {
        console.error('Delete booking error:', error);
        toast.error('Failed to delete booking');
      }
    }
  };

  const handleStatusChange = async (bookingId, newStatus) => {
    try {
      await axios.put(`/api/admin/bookings/${bookingId}/status`, { status: newStatus });
      toast.success('Booking status updated successfully');
      loadBookings();
    } catch (error) {
      console.error('Status change error:', error);
      toast.error('Failed to update booking status');
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      confirmed: { class: 'badge-success', text: 'Confirmed', icon: '✅' },
      completed: { class: 'badge-info', text: 'Completed', icon: '🏁' },
      cancelled: { class: 'badge-danger', text: 'Cancelled', icon: '❌' },
      no_show: { class: 'badge-warning', text: 'No Show', icon: '⚠️' },
      pending: { class: 'badge-secondary', text: 'Pending', icon: '⏳' }
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

  if (loading && bookings.length === 0) {
    return <LoadingSpinner text="Loading bookings..." />;
  }

  return (
    <div style={{ padding: '2rem 0' }}>
      <div className="container">
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '2rem'
        }}>
          <h1 style={{ fontSize: '2rem', fontWeight: '700', color: '#1f2937' }}>
            Booking Management
          </h1>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              onClick={() => setViewMode('list')}
              className={`btn ${viewMode === 'list' ? 'btn-primary' : 'btn-outline'}`}
            >
              List View
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={`btn ${viewMode === 'calendar' ? 'btn-primary' : 'btn-outline'}`}
            >
              Calendar View
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="card" style={{ marginBottom: '2rem' }}>
          <div className="card-header">
            <h3 style={{ margin: 0 }}>Filters</h3>
          </div>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '1rem',
            padding: '1rem'
          }}>
            <div>
              <label className="form-label">Status</label>
              <select
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="form-input"
              >
                <option value="">All Statuses</option>
                <option value="confirmed">Confirmed</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
                <option value="no_show">No Show</option>
                <option value="pending">Pending</option>
              </select>
            </div>

            <div>
              <label className="form-label">Date</label>
              <input
                type="date"
                value={filters.date}
                onChange={(e) => handleFilterChange('date', e.target.value)}
                className="form-input"
              />
            </div>

            <div>
              <label className="form-label">Slot Number</label>
              <input
                type="text"
                placeholder="Enter slot number"
                value={filters.slotNumber}
                onChange={(e) => handleFilterChange('slotNumber', e.target.value)}
                className="form-input"
              />
            </div>

            <div>
              <label className="form-label">Customer Name</label>
              <input
                type="text"
                placeholder="Search by name"
                value={filters.customerName}
                onChange={(e) => handleFilterChange('customerName', e.target.value)}
                className="form-input"
              />
            </div>

            <div>
              <label className="form-label">Payment Status</label>
              <select
                value={filters.paymentStatus}
                onChange={(e) => handleFilterChange('paymentStatus', e.target.value)}
                className="form-input"
              >
                <option value="">All Payment Statuses</option>
                <option value="completed">Paid</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
                <option value="refunded">Refunded</option>
              </select>
            </div>
          </div>
        </div>

        {/* Bulk Actions */}
        {selectedBookings.length > 0 && (
          <div className="card" style={{ marginBottom: '1rem', backgroundColor: '#f0f9ff' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              padding: '1rem'
            }}>
              <span style={{ fontWeight: '600', color: '#0369a1' }}>
                {selectedBookings.length} booking(s) selected
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={() => handleBulkAction('confirm')}
                  className="btn btn-success"
                  style={{ fontSize: '0.875rem' }}
                >
                  Confirm All
                </button>
                <button
                  onClick={() => handleBulkAction('complete')}
                  className="btn btn-info"
                  style={{ fontSize: '0.875rem' }}
                >
                  Complete All
                </button>
                <button
                  onClick={() => handleBulkAction('cancel')}
                  className="btn btn-warning"
                  style={{ fontSize: '0.875rem' }}
                >
                  Cancel All
                </button>
                <button
                  onClick={() => handleBulkAction('delete')}
                  className="btn btn-danger"
                  style={{ fontSize: '0.875rem' }}
                >
                  Delete All
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Calendar View */}
        {viewMode === 'calendar' && (
          <div style={{ marginBottom: '2rem' }}>
            <AdminCalendar 
              selectedDate={selectedDate} 
              onDateSelect={handleDateSelect}
            />
          </div>
        )}

        {/* Bookings List */}
        <div className="card">
          <div className="card-header">
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center'
            }}>
              <h3 style={{ margin: 0 }}>Bookings ({totalBookings})</h3>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={selectAll}
                    onChange={handleSelectAll}
                  />
                  Select All
                </label>
              </div>
            </div>
          </div>

          {bookings.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7280' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📋</div>
              <h3>No bookings found</h3>
              <p>Try adjusting your filters or create a new booking.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1" style={{ gap: '1rem', padding: '1rem' }}>
              {bookings.map((booking) => (
                <div key={booking._id} className="card" style={{
                  border: selectedBookings.includes(booking._id) ? '2px solid #3b82f6' : '1px solid #e5e7eb',
                  backgroundColor: selectedBookings.includes(booking._id) ? '#f0f9ff' : '#ffffff'
                }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                    gap: '1rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: '200px' }}>
                      <input
                        type="checkbox"
                        checked={selectedBookings.includes(booking._id)}
                        onChange={() => handleSelectBooking(booking._id)}
                      />
                      <div>
                        <h4 style={{ margin: '0 0 0.5rem 0', color: '#1f2937' }}>
                          Slot {booking.slotNumber}
                        </h4>
                        <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                          {booking.customerDetails.name}
                        </p>
                        <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                          {booking.customerDetails.email}
                        </p>
                      </div>
                    </div>

                    <div style={{ flex: 1, minWidth: '250px' }}>
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center',
                        marginBottom: '1rem'
                      }}>
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
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {getStatusBadge(booking.status)}
                          {getPaymentStatusBadge(booking.payment.status)}
                        </div>
                      </div>

                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center'
                      }}>
                        <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                          <strong>License:</strong> {booking.vehicleDetails.licensePlate}
                        </p>
                        <p style={{ margin: '0.25rem 0', fontWeight: '600', color: '#059669' }}>
                          LKR {booking.payment.amount}
                        </p>
                      </div>
                    </div>

                    <div style={{ 
                      display: 'flex', 
                      flexDirection: 'column', 
                      gap: '0.5rem',
                      minWidth: '150px'
                    }}>
                      <select
                        value={booking.status}
                        onChange={(e) => handleStatusChange(booking._id, e.target.value)}
                        className="form-input"
                        style={{ fontSize: '0.875rem' }}
                      >
                        <option value="pending">Pending</option>
                        <option value="confirmed">Confirmed</option>
                        <option value="completed">Completed</option>
                        <option value="cancelled">Cancelled</option>
                        <option value="no_show">No Show</option>
                      </select>
                      
                      <button
                        onClick={() => handleDeleteBooking(booking._id)}
                        className="btn btn-danger"
                        style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
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
              disabled={currentPage === 1}
            >
              Previous
            </button>
            
            <span style={{ color: '#6b7280' }}>
              Page {currentPage} of {totalPages}
            </span>
            
            <button
              onClick={() => setCurrentPage(currentPage + 1)}
              className="btn btn-outline"
              disabled={currentPage === totalPages}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminBookingManagement; 