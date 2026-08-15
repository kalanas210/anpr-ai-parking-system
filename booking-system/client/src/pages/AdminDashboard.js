import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import LoadingSpinner from '../components/LoadingSpinner';

const AdminDashboard = () => {
  const [statistics, setStatistics] = useState(null);
  const [recentBookings, setRecentBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoCompletionStatus, setAutoCompletionStatus] = useState(null);
  const [autoCompletionLoading, setAutoCompletionLoading] = useState(false);

  useEffect(() => {
    loadDashboardData();
    loadAutoCompletionStatus();
  }, []);

  const loadDashboardData = async () => {
    try {
      const [statsRes, bookingsRes] = await Promise.all([
        axios.get('/api/admin/statistics'),
        axios.get('/api/admin/bookings?limit=5')
      ]);

      setStatistics(statsRes.data.data);
      setRecentBookings(bookingsRes.data.data.bookings);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAutoCompletionStatus = async () => {
    try {
      const response = await axios.get('/api/admin/auto-completion/status');
      setAutoCompletionStatus(response.data.data);
    } catch (error) {
      console.error('Error loading auto-completion status:', error);
    }
  };

  const handleAutoCompletionAction = async (action) => {
    setAutoCompletionLoading(true);
    try {
      await axios.post(`/api/admin/auto-completion/${action}`);
      await loadAutoCompletionStatus();
      alert(`Auto-completion service ${action}ed successfully`);
    } catch (error) {
      console.error(`Error ${action}ing auto-completion service:`, error);
      alert(`Failed to ${action} auto-completion service`);
    } finally {
      setAutoCompletionLoading(false);
    }
  };

  const handleManualTrigger = async () => {
    setAutoCompletionLoading(true);
    try {
      await axios.post('/api/admin/auto-completion/trigger');
      alert('Auto-completion service triggered successfully');
    } catch (error) {
      console.error('Error triggering auto-completion service:', error);
      alert('Failed to trigger auto-completion service');
    } finally {
      setAutoCompletionLoading(false);
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

  if (loading) {
    return <LoadingSpinner text="Loading dashboard..." />;
  }

  return (
    <div style={{ padding: '2rem 0' }}>
      <div className="container">
        <h1 style={{ fontSize: '2rem', fontWeight: '700', color: '#1f2937', marginBottom: '2rem' }}>
          Admin Dashboard
        </h1>

        {/* Auto-Completion Service Status */}
        <div className="card" style={{ 
          marginBottom: '2rem', 
          backgroundColor: '#f0f9ff',
          border: '1px solid #e0f2fe',
          borderTop: '3px solid #ef4444'
        }}>
          <div className="card-header">
            <h2 className="card-title" style={{ 
              color: '#0369a1',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{ fontSize: '1.25rem' }}>🤖</span>
              Auto-Completion Service
            </h2>
          </div>
          <div style={{ padding: '1.5rem' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '1.5rem',
              flexWrap: 'wrap',
              gap: '1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <strong style={{ color: '#374151' }}>Status:</strong>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.5rem',
                  padding: '0.25rem 0.75rem',
                  borderRadius: '0.375rem',
                  backgroundColor: autoCompletionStatus?.isRunning ? '#dcfce7' : '#fef2f2',
                  border: `1px solid ${autoCompletionStatus?.isRunning ? '#bbf7d0' : '#fecaca'}`
                }}>
                  <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: autoCompletionStatus?.isRunning ? '#16a34a' : '#ef4444'
                  }}></div>
                  <span style={{ 
                    color: autoCompletionStatus?.isRunning ? '#15803d' : '#dc2626',
                    fontWeight: '600',
                    fontSize: '0.875rem'
                  }}>
                    {autoCompletionStatus?.isRunning ? 'Running' : 'Stopped'}
                  </span>
                </div>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <strong style={{ color: '#374151' }}>Last Check:</strong>
                <span style={{ 
                  color: '#6b7280',
                  fontSize: '0.875rem'
                }}>
                  {autoCompletionStatus?.lastCheck ? 
                    new Date(autoCompletionStatus.lastCheck).toLocaleString() : 
                    'Never'
                  }
                </span>
              </div>
            </div>
            
            <div style={{ 
              display: 'flex', 
              gap: '1rem', 
              flexWrap: 'wrap',
              marginBottom: '1.5rem'
            }}>
              <button
                onClick={() => handleAutoCompletionAction('start')}
                disabled={autoCompletionLoading || autoCompletionStatus?.isRunning}
                className="btn"
                style={{ 
                  fontSize: '0.875rem',
                  backgroundColor: '#10b981',
                  color: 'white',
                  border: 'none',
                  padding: '0.75rem 1.5rem',
                  borderRadius: '0.375rem',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  cursor: autoCompletionLoading || autoCompletionStatus?.isRunning ? 'not-allowed' : 'pointer',
                  opacity: autoCompletionLoading || autoCompletionStatus?.isRunning ? 0.6 : 1,
                  transition: 'all 0.2s ease'
                }}
              >
                <span style={{ fontSize: '1rem' }}>▶️</span>
                START SERVICE
              </button>
              
              <button
                onClick={() => handleAutoCompletionAction('stop')}
                disabled={autoCompletionLoading || !autoCompletionStatus?.isRunning}
                className="btn"
                style={{ 
                  fontSize: '0.875rem',
                  backgroundColor: '#fecaca',
                  color: '#dc2626',
                  border: '1px solid #fca5a5',
                  padding: '0.75rem 1.5rem',
                  borderRadius: '0.375rem',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  cursor: autoCompletionLoading || !autoCompletionStatus?.isRunning ? 'not-allowed' : 'pointer',
                  opacity: autoCompletionLoading || !autoCompletionStatus?.isRunning ? 0.6 : 1,
                  transition: 'all 0.2s ease'
                }}
              >
                <span style={{ fontSize: '1rem' }}>⏹️</span>
                STOP SERVICE
              </button>
              
              <button
                onClick={handleManualTrigger}
                disabled={autoCompletionLoading}
                className="btn"
                style={{ 
                  fontSize: '0.875rem',
                  backgroundColor: '#dc2626',
                  color: 'white',
                  border: 'none',
                  padding: '0.75rem 1.5rem',
                  borderRadius: '0.375rem',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  cursor: autoCompletionLoading ? 'not-allowed' : 'pointer',
                  opacity: autoCompletionLoading ? 0.6 : 1,
                  transition: 'all 0.2s ease'
                }}
              >
                <span style={{ fontSize: '1rem' }}>⚡</span>
                MANUAL TRIGGER
              </button>
            </div>
            
            <div style={{ 
              padding: '1rem', 
              backgroundColor: '#e0f2fe', 
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
              color: '#01579b',
              border: '1px solid #b3e5fc'
            }}>
              <strong>Service Info:</strong> Automatically completes expired bookings and updates slot status every minute. 
              Slot status is updated every 5 minutes based on current bookings.
            </div>
          </div>
        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-4" style={{ gap: '1rem', marginBottom: '2rem' }}>
          <div className="card" style={{ textAlign: 'center' }}>
            <h3 style={{ fontSize: '2rem', fontWeight: '700', color: '#3b82f6', margin: '0 0 0.5rem 0' }}>
              {statistics?.today?.bookings || 0}
            </h3>
            <p style={{ margin: 0, color: '#6b7280' }}>Today's Bookings</p>
          </div>

          <div className="card" style={{ textAlign: 'center' }}>
            <h3 style={{ fontSize: '2rem', fontWeight: '700', color: '#10b981', margin: '0 0 0.5rem 0' }}>
              LKR {statistics?.today?.revenue || 0}
            </h3>
            <p style={{ margin: 0, color: '#6b7280' }}>Today's Revenue</p>
          </div>

          <div className="card" style={{ textAlign: 'center' }}>
            <h3 style={{ fontSize: '2rem', fontWeight: '700', color: '#f59e0b', margin: '0 0 0.5rem 0' }}>
              {statistics?.month?.bookings || 0}
            </h3>
            <p style={{ margin: 0, color: '#6b7280' }}>This Month</p>
          </div>

          <div className="card" style={{ textAlign: 'center' }}>
            <h3 style={{ fontSize: '2rem', fontWeight: '700', color: '#8b5cf6', margin: '0 0 0.5rem 0' }}>
              LKR {statistics?.month?.revenue || 0}
            </h3>
            <p style={{ margin: 0, color: '#6b7280' }}>Monthly Revenue</p>
          </div>
        </div>

        {/* Recent Bookings */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Recent Bookings</h2>
          </div>

          {recentBookings.length === 0 ? (
            <p style={{ textAlign: 'center', color: '#6b7280', padding: '2rem' }}>
              No recent bookings found
            </p>
          ) : (
            <div className="grid grid-cols-1" style={{ gap: '1rem' }}>
              {recentBookings.map((booking) => (
                <div key={booking._id} style={{
                  border: '1px solid #e5e7eb',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  backgroundColor: '#f9fafb'
                }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '1rem'
                  }}>
                    <div>
                      <h4 style={{ margin: '0 0 0.5rem 0', color: '#1f2937' }}>
                        {booking.slotNumber} - {booking.customerDetails.name}
                      </h4>
                      <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                        {new Date(booking.date).toLocaleDateString()} | {booking.startTime} - {booking.endTime}
                      </p>
                      <p style={{ margin: '0.25rem 0', color: '#6b7280', fontSize: '0.875rem' }}>
                        {booking.vehicleDetails.make} {booking.vehicleDetails.model} ({booking.vehicleDetails.licensePlate})
                      </p>
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
                      {getStatusBadge(booking.status)}
                      <p style={{ margin: 0, fontWeight: '600', color: '#3b82f6' }}>
                        LKR {booking.payment.amount}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card" style={{ marginTop: '2rem' }}>
          <div className="card-header">
            <h2 className="card-title">Quick Actions</h2>
          </div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <Link to="/admin/bookings" className="btn btn-primary">
              Manage Bookings
            </Link>
            <button className="btn btn-outline">
              Manage Users
            </button>
            <button className="btn btn-outline">
              System Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard; 