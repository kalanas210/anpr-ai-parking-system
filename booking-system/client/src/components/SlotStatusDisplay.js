import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SlotStatusDisplay = ({ date, startTime, endTime }) => {
  const [slotStatus, setSlotStatus] = useState({
    slot1: { status: 'unknown', lastUpdated: null },
    slot2: { status: 'unknown', lastUpdated: null }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(null);

  // Always fetch current live status, regardless of selected booking time
  useEffect(() => {
    fetchCurrentStatus();
  }, []); // Only run once on component mount

  // Auto-refresh functionality - always refresh current status
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchCurrentStatus();
      }, 5000); // Refresh every 5 seconds
      
      setRefreshInterval(interval);
      
      return () => {
        if (interval) {
          clearInterval(interval);
        }
      };
    } else {
      // Clear interval if auto-refresh is disabled
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }
  }, [autoRefresh]);



  const fetchCurrentStatus = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // First try to get real-time status from main parking system
      const realtimeResponse = await axios.get('/api/parking/realtime-status');
      
      if (realtimeResponse.data.success) {
        setSlotStatus(realtimeResponse.data.data);
        return;
      }
    } catch (error) {
      console.log('Real-time status not available, falling back to booking system status');
    }
    
    try {
      // Fallback to booking system status
      const now = new Date();
      const today = now.toISOString().split('T')[0];
      const currentTime = now.toTimeString().split(' ')[0].substring(0, 5);
      
      const response = await axios.get('/api/slots/status', {
        params: {
          date: today,
          startTime: currentTime,
          endTime: currentTime
        }
      });
      
      setSlotStatus(response.data.data);
    } catch (error) {
      console.error('Error fetching current slot status:', error);
      setError('Failed to load current slot status. Please ensure the main parking system (app.py or app_video.py) is running.');
      // Set default status for demo purposes
      setSlotStatus({
        slot1: { status: 'unknown', lastUpdated: new Date().toISOString(), message: 'System offline' },
        slot2: { status: 'unknown', lastUpdated: new Date().toISOString(), message: 'System offline' }
      });
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'free':
        return '#10b981'; // Green
      case 'busy':
        return '#ef4444'; // Red
      case 'unknown':
        return '#6b7280'; // Gray
      default:
        return '#6b7280';
    }
  };

  const getStatusText = (status, slotData) => {
    switch (status) {
      case 'free':
        return '🟢 Free';
      case 'busy':
        return '🔴 Busy';
      case 'unknown':
        return '⚪ Unknown';
      default:
        return '⚪ Unknown';
    }
  };

  const getStatusDetails = (slotData) => {
    if (!slotData) return null;
    
    if (slotData.status === 'busy' && slotData.licensePlate) {
      return {
        licensePlate: slotData.licensePlate,
        vehicleType: slotData.vehicleType,
        entryTime: slotData.entryTime,
        parkingDuration: slotData.parkingDuration
      };
    }
    
    return null;
  };

  const formatLastUpdated = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  };

  // Always show the component, even without date/time selection

  return (
    <div style={{
      backgroundColor: '#f8fafc',
      border: '1px solid #e2e8f0',
      borderRadius: '0.5rem',
      padding: '1rem',
      marginTop: '1rem'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0.75rem'
      }}>
        <h4 style={{ margin: 0, color: '#1e293b', fontSize: '1rem' }}>
          📍 Current Live Slot Status
        </h4>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.25rem', 
            fontSize: '0.75rem',
            cursor: 'pointer'
          }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{ margin: 0 }}
            />
            Auto-refresh
          </label>
          <button
            onClick={fetchCurrentStatus}
            disabled={loading}
            style={{
              background: 'none',
              border: '1px solid #d1d5db',
              borderRadius: '0.25rem',
              padding: '0.25rem 0.5rem',
              fontSize: '0.75rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? '🔄' : '🔄 Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          backgroundColor: '#fee2e2',
          color: '#991b1b',
          padding: '0.5rem',
          borderRadius: '0.25rem',
          fontSize: '0.875rem',
          marginBottom: '0.75rem'
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Slot 1 */}
        <div style={{
          backgroundColor: 'white',
          border: '1px solid #e2e8f0',
          borderRadius: '0.375rem',
          padding: '0.75rem',
          textAlign: 'center'
        }}>
          <div style={{
            fontSize: '1.25rem',
            fontWeight: 'bold',
            marginBottom: '0.5rem',
            color: '#1e293b'
          }}>
            Slot 1
          </div>
          <div style={{
            fontSize: '1rem',
            fontWeight: '600',
            color: getStatusColor(slotStatus.slot1.status),
            marginBottom: '0.25rem'
          }}>
            {getStatusText(slotStatus.slot1.status, slotStatus.slot1)}
          </div>
          {slotStatus.slot1.message && (
            <div style={{
              fontSize: '0.75rem',
              color: '#6b7280',
              marginBottom: '0.25rem'
            }}>
              {slotStatus.slot1.message}
            </div>
          )}
          {getStatusDetails(slotStatus.slot1) && (
            <div style={{
              fontSize: '0.75rem',
              color: '#374151',
              marginBottom: '0.25rem',
              textAlign: 'left'
            }}>
              <div><strong>Plate:</strong> {getStatusDetails(slotStatus.slot1).licensePlate}</div>
              <div><strong>Type:</strong> {getStatusDetails(slotStatus.slot1).vehicleType}</div>
              {getStatusDetails(slotStatus.slot1).entryTime && (
                <div><strong>Entry:</strong> {new Date(getStatusDetails(slotStatus.slot1).entryTime).toLocaleTimeString()}</div>
              )}
            </div>
          )}
          <div style={{
            fontSize: '0.75rem',
            color: '#6b7280'
          }}>
            Updated: {formatLastUpdated(slotStatus.slot1.lastUpdated)}
          </div>
        </div>

        {/* Slot 2 */}
        <div style={{
          backgroundColor: 'white',
          border: '1px solid #e2e8f0',
          borderRadius: '0.375rem',
          padding: '0.75rem',
          textAlign: 'center'
        }}>
          <div style={{
            fontSize: '1.25rem',
            fontWeight: 'bold',
            marginBottom: '0.5rem',
            color: '#1e293b'
          }}>
            Slot 2
          </div>
          <div style={{
            fontSize: '1rem',
            fontWeight: '600',
            color: getStatusColor(slotStatus.slot2.status),
            marginBottom: '0.25rem'
          }}>
            {getStatusText(slotStatus.slot2.status, slotStatus.slot2)}
          </div>
          {slotStatus.slot2.message && (
            <div style={{
              fontSize: '0.75rem',
              color: '#6b7280',
              marginBottom: '0.25rem'
            }}>
              {slotStatus.slot2.message}
            </div>
          )}
          {getStatusDetails(slotStatus.slot2) && (
            <div style={{
              fontSize: '0.75rem',
              color: '#374151',
              marginBottom: '0.25rem',
              textAlign: 'left'
            }}>
              <div><strong>Plate:</strong> {getStatusDetails(slotStatus.slot2).licensePlate}</div>
              <div><strong>Type:</strong> {getStatusDetails(slotStatus.slot2).vehicleType}</div>
              {getStatusDetails(slotStatus.slot2).entryTime && (
                <div><strong>Entry:</strong> {new Date(getStatusDetails(slotStatus.slot2).entryTime).toLocaleTimeString()}</div>
              )}
            </div>
          )}
          <div style={{
            fontSize: '0.75rem',
            color: '#6b7280'
          }}>
            Updated: {formatLastUpdated(slotStatus.slot2.lastUpdated)}
          </div>
        </div>
      </div>

              <div style={{
          marginTop: '0.75rem',
          padding: '0.5rem',
          backgroundColor: '#f0f9ff',
          borderRadius: '0.25rem',
          fontSize: '0.75rem',
          color: '#0369a1'
        }}>
          <strong>Note:</strong> 
          Always showing current real-time status from main parking system (app.py/app_video.py). 
          If system is offline, please start the main parking system first.
          Manual refresh available for real-time updates.
        </div>
        
        {/* Today's booking warning */}
        {(slotStatus.slot1.status === 'busy' || slotStatus.slot2.status === 'busy') && (
          <div style={{
            marginTop: '0.5rem',
            padding: '0.5rem',
            backgroundColor: '#fef3c7',
            borderRadius: '0.25rem',
            fontSize: '0.75rem',
            color: '#92400e',
            border: '1px solid #f59e0b'
          }}>
            <strong>⚠️ Today's Booking Restriction:</strong> 
            Busy slots cannot be booked for today as we don't know when vehicles will leave. You can still book them for future dates.
          </div>
        )}
    </div>
  );
};

export default SlotStatusDisplay; 