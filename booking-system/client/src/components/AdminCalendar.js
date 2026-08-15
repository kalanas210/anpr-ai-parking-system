import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const AdminCalendar = ({ selectedDate, onDateSelect }) => {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentMonth, setCurrentMonth] = useState(new Date());

  useEffect(() => {
    loadMonthBookings();
  }, [currentMonth]);

  const loadMonthBookings = async () => {
    try {
      setLoading(true);
      const startOfMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
      const endOfMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);
      
      const response = await axios.get(`/api/admin/bookings?startDate=${startOfMonth.toISOString()}&endDate=${endOfMonth.toISOString()}&limit=1000`);
      setBookings(response.data.data.bookings);
    } catch (error) {
      console.error('Error loading month bookings:', error);
      toast.error('Failed to load calendar data');
    } finally {
      setLoading(false);
    }
  };

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();
    
    const days = [];
    
    // Add empty cells for days before the first day of the month
    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push(null);
    }
    
    // Add all days of the month
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(year, month, i));
    }
    
    return days;
  };

  const getBookingsForDate = (date) => {
    if (!date) return [];
    const dateStr = date.toISOString().split('T')[0];
    return bookings.filter(booking => {
      const bookingDate = new Date(booking.date).toISOString().split('T')[0];
      return bookingDate === dateStr;
    });
  };

  const getStatusColor = (status) => {
    const colors = {
      confirmed: '#10b981',
      completed: '#3b82f6',
      cancelled: '#ef4444',
      no_show: '#f59e0b',
      pending: '#6b7280'
    };
    return colors[status] || '#6b7280';
  };

  const formatTime = (time) => {
    return time.substring(0, 5); // Show only HH:MM
  };

  const handleDateClick = (date) => {
    if (date) {
      const selectedDateStr = date.toISOString().split('T')[0];
      console.log('Calendar: Date clicked:', selectedDateStr);
      onDateSelect(selectedDateStr);
    }
  };

  const goToPreviousMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };

  const goToNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };

  const goToToday = () => {
    setCurrentMonth(new Date());
  };

  const days = getDaysInMonth(currentMonth);
  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  return (
    <div className="card">
      <div className="card-header">
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center'
        }}>
          <h3 style={{ margin: 0 }}>Calendar View</h3>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button onClick={goToPreviousMonth} className="btn btn-outline" style={{ fontSize: '0.875rem' }}>
              ←
            </button>
            <button onClick={goToToday} className="btn btn-primary" style={{ fontSize: '0.875rem' }}>
              Today
            </button>
            <button onClick={goToNextMonth} className="btn btn-outline" style={{ fontSize: '0.875rem' }}>
              →
            </button>
          </div>
        </div>
        <h4 style={{ margin: '0.5rem 0 0 0', color: '#6b7280' }}>
          {monthNames[currentMonth.getMonth()]} {currentMonth.getFullYear()}
        </h4>
      </div>

      <div style={{ padding: '1rem' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <div className="loading"></div>
            <p>Loading calendar...</p>
          </div>
        ) : (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(7, 1fr)', 
            gap: '1px',
            backgroundColor: '#e5e7eb',
            border: '1px solid #e5e7eb'
          }}>
            {/* Week day headers */}
            {weekDays.map(day => (
              <div key={day} style={{
                backgroundColor: '#f9fafb',
                padding: '0.75rem',
                textAlign: 'center',
                fontWeight: '600',
                fontSize: '0.875rem',
                color: '#374151'
              }}>
                {day}
              </div>
            ))}

            {/* Calendar days */}
            {days.map((date, index) => {
              const dayBookings = getBookingsForDate(date);
              const isToday = date && date.toDateString() === new Date().toDateString();
              const isSelected = date && selectedDate === date.toISOString().split('T')[0];

              return (
                <div
                  key={index}
                  onClick={() => handleDateClick(date)}
                  style={{
                    backgroundColor: isSelected ? '#f0f9ff' : '#ffffff',
                    minHeight: '120px',
                    padding: '0.5rem',
                    cursor: date ? 'pointer' : 'default',
                    border: isToday ? '2px solid #3b82f6' : isSelected ? '2px solid #3b82f6' : '1px solid #e5e7eb',
                    position: 'relative',
                    transition: 'all 0.2s ease-in-out'
                  }}
                >
                  {date && (
                    <>
                      <div style={{
                        fontWeight: isToday ? '700' : '500',
                        color: isToday ? '#3b82f6' : '#374151',
                        fontSize: '0.875rem',
                        marginBottom: '0.5rem'
                      }}>
                        {date.getDate()}
                      </div>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        {dayBookings.slice(0, 3).map((booking, bookingIndex) => (
                          <div
                            key={booking._id}
                            style={{
                              backgroundColor: getStatusColor(booking.status),
                              color: 'white',
                              padding: '0.25rem 0.5rem',
                              borderRadius: '0.25rem',
                              fontSize: '0.75rem',
                              fontWeight: '500',
                              cursor: 'pointer',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap'
                            }}
                            title={`Slot ${booking.slotNumber} - ${booking.customerDetails.name} (${formatTime(booking.startTime)})`}
                          >
                            {booking.slotNumber} - {formatTime(booking.startTime)}
                          </div>
                        ))}
                        
                        {dayBookings.length > 3 && (
                          <div style={{
                            backgroundColor: '#6b7280',
                            color: 'white',
                            padding: '0.25rem 0.5rem',
                            borderRadius: '0.25rem',
                            fontSize: '0.75rem',
                            textAlign: 'center'
                          }}>
                            +{dayBookings.length - 3} more
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ 
        padding: '1rem', 
        borderTop: '1px solid #e5e7eb',
        backgroundColor: '#f9fafb'
      }}>
        <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem' }}>Legend</h4>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ 
              width: '12px', 
              height: '12px', 
              backgroundColor: '#10b981', 
              borderRadius: '2px' 
            }}></div>
            <span style={{ fontSize: '0.75rem' }}>Confirmed</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ 
              width: '12px', 
              height: '12px', 
              backgroundColor: '#3b82f6', 
              borderRadius: '2px' 
            }}></div>
            <span style={{ fontSize: '0.75rem' }}>Completed</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ 
              width: '12px', 
              height: '12px', 
              backgroundColor: '#ef4444', 
              borderRadius: '2px' 
            }}></div>
            <span style={{ fontSize: '0.75rem' }}>Cancelled</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ 
              width: '12px', 
              height: '12px', 
              backgroundColor: '#f59e0b', 
              borderRadius: '2px' 
            }}></div>
            <span style={{ fontSize: '0.75rem' }}>No Show</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ 
              width: '12px', 
              height: '12px', 
              backgroundColor: '#6b7280', 
              borderRadius: '2px' 
            }}></div>
            <span style={{ fontSize: '0.75rem' }}>Pending</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminCalendar; 