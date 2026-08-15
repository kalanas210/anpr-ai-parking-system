import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBooking } from '../contexts/BookingContext';
import PaymentForm from '../components/PaymentForm';
import LoadingSpinner from '../components/LoadingSpinner';
import SlotStatusDisplay from '../components/SlotStatusDisplay';
import { toast } from 'react-toastify';

const BookingForm = () => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    date: '',
    startTime: '',
    endTime: '',
    slotNumber: '',
    vehicleDetails: {
      make: '',
      model: '',
      color: '',
      licensePlate: ''
    },
    customerDetails: {
      name: '',
      phone: '',
      email: ''
    }
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentBooking, setCurrentBooking] = useState(null);

  const { user } = useAuth();
  const { getAvailableSlots, createBooking, calculatePrice, loading, availableSlots } = useBooking();
  const navigate = useNavigate();

  // Pre-fill customer details from user profile
  useEffect(() => {
    if (user) {
      setFormData(prev => ({
        ...prev,
        customerDetails: {
          name: user.name,
          phone: user.phone,
          email: user.email
        }
      }));
    }
  }, [user]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    if (name.includes('.')) {
      const [section, field] = name.split('.');
      setFormData(prev => ({
        ...prev,
        [section]: {
          ...prev[section],
          [field]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
    }

    // Clear errors when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateStep1 = () => {
    const newErrors = {};

    if (!formData.date) {
      newErrors.date = 'Date is required';
    } else {
      const selectedDate = new Date(formData.date);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      if (selectedDate < today) {
        newErrors.date = 'Date cannot be in the past';
      }
    }

    if (!formData.startTime) {
      newErrors.startTime = 'Start time is required';
    }

    if (!formData.endTime) {
      newErrors.endTime = 'End time is required';
    } else if (formData.startTime && formData.endTime) {
      const start = new Date(`2000-01-01T${formData.startTime}`);
      const end = new Date(`2000-01-01T${formData.endTime}`);
      
      if (end <= start) {
        newErrors.endTime = 'End time must be after start time';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = () => {
    const newErrors = {};

    if (!formData.slotNumber) {
      newErrors.slotNumber = 'Please select a slot';
    }

    if (!formData.vehicleDetails.make) {
      newErrors['vehicleDetails.make'] = 'Vehicle make is required';
    }

    if (!formData.vehicleDetails.model) {
      newErrors['vehicleDetails.model'] = 'Vehicle model is required';
    }

    if (!formData.vehicleDetails.color) {
      newErrors['vehicleDetails.color'] = 'Vehicle color is required';
    }

    if (!formData.vehicleDetails.licensePlate) {
      newErrors['vehicleDetails.licensePlate'] = 'License plate is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = async () => {
    if (step === 1) {
      if (!validateStep1()) return;
      
      // Get available slots
      const slotsData = await getAvailableSlots(formData.date, formData.startTime, formData.endTime);
      if (!slotsData || slotsData.availableSlots.length === 0) {
        setErrors({ general: 'No slots available for the selected time. Please choose a different time.' });
        return;
      }
      
      setStep(2);
    } else if (step === 2) {
      if (!validateStep2()) return;
      setStep(3);
    }
  };

  const handleBack = () => {
    setStep(step - 1);
  };

  const handleSlotSelect = (slot) => {
    setFormData(prev => ({
      ...prev,
      slotNumber: slot
    }));
  };

  const handleCreateBooking = async () => {
    setIsSubmitting(true);
    
    try {
      console.log('Starting booking creation...');
      
      // Check for existing bookings at the same time
      const existingBookings = await checkExistingBookings();
      if (existingBookings && existingBookings.length > 0) {
        toast.error('You already have a booking at this time. Please choose a different time or cancel your existing booking.');
        setIsSubmitting(false);
        return;
      }

      const price = calculatePrice(formData.startTime, formData.endTime);
      console.log('Calculated price:', price);
      
      const bookingData = {
        ...formData,
        payment: {
          amount: price,
          currency: 'LKR'
        }
      };
      
      console.log('Booking data to send:', bookingData);

      const result = await createBooking(bookingData);
      console.log('Booking creation result:', result);
      
      if (result.success) {
        setCurrentBooking(result.booking);
        console.log('Booking created:', result.booking);
        toast.success('Booking created successfully! Proceed to payment.');
      } else {
        console.error('Booking creation failed:', result);
        toast.error('Failed to create booking. Please try again.');
      }
    } catch (error) {
      console.error('Create booking error:', error);
      toast.error('An error occurred while creating the booking.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Check for existing bookings at the same time
  const checkExistingBookings = async () => {
    try {
      const response = await fetch('/api/bookings/my-bookings', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const bookings = data.data.bookings || [];
        
        // Filter bookings that overlap with the current time slot
        const overlappingBookings = bookings.filter(booking => {
          if (booking.status === 'cancelled') return false;
          
          const bookingDate = booking.date.split('T')[0];
          const currentDate = formData.date;
          
          if (bookingDate !== currentDate) return false;
          
          // Check for time overlap
          const bookingStart = booking.startTime;
          const bookingEnd = booking.endTime;
          const currentStart = formData.startTime;
          const currentEnd = formData.endTime;
          
          // Check if times overlap
          return !(currentEnd <= bookingStart || currentStart >= bookingEnd);
        });
        
        return overlappingBookings;
      }
    } catch (error) {
      console.error('Error checking existing bookings:', error);
    }
    return [];
  };

  const getAvailableSlotsForDisplay = () => {
    if (!formData.date || !formData.startTime || !formData.endTime) return [];
    return availableSlots;
  };

  const price = calculatePrice(formData.startTime, formData.endTime);

  if (loading) {
    return <LoadingSpinner text="Loading available slots..." />;
  }

  return (
    <div style={{ padding: '2rem 0' }}>
      <div className="container">
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          {/* Progress Steps */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            marginBottom: '2rem',
            position: 'relative'
          }}>
            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center',
              flex: 1
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: step >= 1 ? '#3b82f6' : '#e5e7eb',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                marginBottom: '0.5rem'
              }}>
                1
              </div>
              <span style={{ fontSize: '0.875rem', color: step >= 1 ? '#3b82f6' : '#6b7280' }}>
                Date & Time
              </span>
            </div>
            
            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center',
              flex: 1
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: step >= 2 ? '#3b82f6' : '#e5e7eb',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                marginBottom: '0.5rem'
              }}>
                2
              </div>
              <span style={{ fontSize: '0.875rem', color: step >= 2 ? '#3b82f6' : '#6b7280' }}>
                Slot & Vehicle
              </span>
            </div>
            
            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center',
              flex: 1
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: step >= 3 ? '#3b82f6' : '#e5e7eb',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                marginBottom: '0.5rem'
              }}>
                3
              </div>
              <span style={{ fontSize: '0.875rem', color: step >= 3 ? '#3b82f6' : '#6b7280' }}>
                Payment
              </span>
            </div>
          </div>

          {/* Step 1: Date and Time Selection */}
          {step === 1 && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Select Date and Time</h2>
              </div>

              <div className="grid grid-cols-3">
                <div className="form-group">
                  <label htmlFor="date" className="form-label">Date</label>
                  <input
                    type="date"
                    id="date"
                    name="date"
                    value={formData.date}
                    onChange={handleChange}
                    className={`form-input ${errors.date ? 'error' : ''}`}
                    min={new Date().toISOString().split('T')[0]}
                  />
                  {errors.date && <div className="error-message">{errors.date}</div>}
                </div>

                <div className="form-group">
                  <label htmlFor="startTime" className="form-label">Start Time</label>
                  <input
                    type="time"
                    id="startTime"
                    name="startTime"
                    value={formData.startTime}
                    onChange={handleChange}
                    className={`form-input ${errors.startTime ? 'error' : ''}`}
                  />
                  {errors.startTime && <div className="error-message">{errors.startTime}</div>}
                </div>

                <div className="form-group">
                  <label htmlFor="endTime" className="form-label">End Time</label>
                  <input
                    type="time"
                    id="endTime"
                    name="endTime"
                    value={formData.endTime}
                    onChange={handleChange}
                    className={`form-input ${errors.endTime ? 'error' : ''}`}
                  />
                  {errors.endTime && <div className="error-message">{errors.endTime}</div>}
                </div>
              </div>

              {/* Slot Status Display - Always visible */}
              <SlotStatusDisplay 
                date={formData.date}
                startTime={formData.startTime}
                endTime={formData.endTime}
              />

              {/* Price Estimate - Only show when date and time are selected */}
              {formData.date && formData.startTime && formData.endTime && (
                <div style={{ 
                  backgroundColor: '#f0f9ff', 
                  padding: '1rem', 
                  borderRadius: '0.5rem',
                  marginTop: '1rem'
                }}>
                  <p style={{ margin: 0, color: '#0369a1' }}>
                    <strong>Estimated Price:</strong> LKR {price} ({Math.ceil((new Date(`2000-01-01T${formData.endTime}`) - new Date(`2000-01-01T${formData.startTime}`)) / (1000 * 60 * 60))} hours)
                  </p>
                </div>
              )}

              <div style={{ marginTop: '2rem', textAlign: 'right' }}>
                <button
                  onClick={handleNext}
                  className="btn btn-primary"
                  disabled={!formData.date || !formData.startTime || !formData.endTime}
                >
                  Next: Select Slot
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Slot and Vehicle Details */}
          {step === 2 && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Select Slot and Vehicle Details</h2>
              </div>

                             {/* Available Slots */}
               <div className="form-group">
                 <label className="form-label">Available Slots</label>
                 
                                   {/* Today's booking warning */}
                  {formData.date === new Date().toISOString().split('T')[0] && (
                    <div style={{
                      marginBottom: '1rem',
                      padding: '0.75rem',
                      backgroundColor: '#fef3c7',
                      borderRadius: '0.5rem',
                      fontSize: '0.875rem',
                      color: '#92400e',
                      border: '1px solid #f59e0b'
                    }}>
                      <strong>⚠️ Today's Booking Notice:</strong> 
                      Slots that are currently occupied by vehicles cannot be booked for today as we don't know when they will leave. 
                      You can still book them for future dates.
                    </div>
                  )}
                 
                 <div className="grid grid-cols-2" style={{ gap: '0.5rem' }}>
                   {getAvailableSlotsForDisplay().availableSlots?.map((slot) => (
                    <button
                      key={slot}
                      type="button"
                      onClick={() => handleSlotSelect(slot)}
                      style={{
                        padding: '0.75rem',
                        border: formData.slotNumber === slot ? '2px solid #3b82f6' : '1px solid #d1d5db',
                        borderRadius: '0.5rem',
                        backgroundColor: formData.slotNumber === slot ? '#eff6ff' : 'white',
                        color: formData.slotNumber === slot ? '#3b82f6' : '#374151',
                        cursor: 'pointer',
                        fontWeight: formData.slotNumber === slot ? '600' : '400'
                      }}
                    >
                      {slot}
                    </button>
                  ))}
                </div>
                {errors.slotNumber && <div className="error-message">{errors.slotNumber}</div>}
              </div>

              {/* Vehicle Details */}
              <div className="grid grid-cols-2">
                <div className="form-group">
                  <label htmlFor="vehicleMake" className="form-label">Vehicle Make</label>
                  <input
                    type="text"
                    id="vehicleMake"
                    name="vehicleDetails.make"
                    value={formData.vehicleDetails.make}
                    onChange={handleChange}
                    className={`form-input ${errors['vehicleDetails.make'] ? 'error' : ''}`}
                    placeholder="e.g., Toyota"
                  />
                  {errors['vehicleDetails.make'] && <div className="error-message">{errors['vehicleDetails.make']}</div>}
                </div>

                <div className="form-group">
                  <label htmlFor="vehicleModel" className="form-label">Vehicle Model</label>
                  <input
                    type="text"
                    id="vehicleModel"
                    name="vehicleDetails.model"
                    value={formData.vehicleDetails.model}
                    onChange={handleChange}
                    className={`form-input ${errors['vehicleDetails.model'] ? 'error' : ''}`}
                    placeholder="e.g., Camry"
                  />
                  {errors['vehicleDetails.model'] && <div className="error-message">{errors['vehicleDetails.model']}</div>}
                </div>

                <div className="form-group">
                  <label htmlFor="vehicleColor" className="form-label">Vehicle Color</label>
                  <input
                    type="text"
                    id="vehicleColor"
                    name="vehicleDetails.color"
                    value={formData.vehicleDetails.color}
                    onChange={handleChange}
                    className={`form-input ${errors['vehicleDetails.color'] ? 'error' : ''}`}
                    placeholder="e.g., Red"
                  />
                  {errors['vehicleDetails.color'] && <div className="error-message">{errors['vehicleDetails.color']}</div>}
                </div>

                <div className="form-group">
                  <label htmlFor="licensePlate" className="form-label">License Plate</label>
                  <input
                    type="text"
                    id="licensePlate"
                    name="vehicleDetails.licensePlate"
                    value={formData.vehicleDetails.licensePlate}
                    onChange={handleChange}
                    className={`form-input ${errors['vehicleDetails.licensePlate'] ? 'error' : ''}`}
                    placeholder="e.g., ABC123"
                    style={{ textTransform: 'uppercase' }}
                  />
                  {errors['vehicleDetails.licensePlate'] && <div className="error-message">{errors['vehicleDetails.licensePlate']}</div>}
                </div>
              </div>

              <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'space-between' }}>
                <button onClick={handleBack} className="btn btn-secondary">
                  Back
                </button>
                <button onClick={handleNext} className="btn btn-primary">
                  Next: Payment
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Payment */}
          {step === 3 && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Complete Payment</h2>
              </div>

                             {/* Booking Summary */}
               <div style={{ 
                 backgroundColor: '#f8fafc', 
                 padding: '1.5rem', 
                 borderRadius: '0.5rem',
                 marginBottom: '2rem'
               }}>
                 <h3 style={{ marginBottom: '1rem', color: '#1f2937' }}>Booking Summary</h3>
                 {currentBooking && (
                   <div style={{ 
                     backgroundColor: '#dbeafe', 
                     padding: '0.75rem', 
                     borderRadius: '0.5rem',
                     marginBottom: '1rem',
                     textAlign: 'center'
                   }}>
                     <p style={{ margin: 0, color: '#1e40af', fontWeight: 'bold' }}>
                       Order ID: {currentBooking.orderId}
                     </p>
                   </div>
                 )}
                 <div className="grid grid-cols-2" style={{ gap: '1rem' }}>
                   <div>
                     <p><strong>Date:</strong> {new Date(formData.date).toLocaleDateString()}</p>
                     <p><strong>Time:</strong> {formData.startTime} - {formData.endTime}</p>
                     <p><strong>Slot:</strong> {formData.slotNumber}</p>
                   </div>
                   <div>
                     <p><strong>Vehicle:</strong> {formData.vehicleDetails.make} {formData.vehicleDetails.model}</p>
                     <p><strong>Color:</strong> {formData.vehicleDetails.color}</p>
                     <p><strong>License:</strong> {formData.vehicleDetails.licensePlate}</p>
                   </div>
                 </div>
                                 <div style={{ 
                   borderTop: '1px solid #e5e7eb', 
                   marginTop: '1rem', 
                   paddingTop: '1rem',
                   textAlign: 'right'
                 }}>
                   <h3 style={{ color: '#3b82f6', margin: 0 }}>Total: LKR {price}</h3>
                 </div>
              </div>

              {!currentBooking ? (
                <button
                  onClick={handleCreateBooking}
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <div className="loading" style={{ marginRight: '0.5rem' }}></div>
                      Creating Booking...
                    </>
                  ) : (
                    'Create Booking & Proceed to Payment'
                  )}
                </button>
              ) : (
                <PaymentForm 
                  booking={currentBooking}
                  onSuccess={() => navigate('/my-bookings')}
                />
              )}

              <div style={{ marginTop: '1rem', textAlign: 'center' }}>
                <button onClick={handleBack} className="btn btn-outline">
                  Back
                </button>
              </div>
            </div>
          )}

          {errors.general && (
            <div style={{ 
              backgroundColor: '#fee2e2', 
              color: '#991b1b', 
              padding: '1rem', 
              borderRadius: '0.5rem',
              marginTop: '1rem'
            }}>
              {errors.general}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BookingForm; 