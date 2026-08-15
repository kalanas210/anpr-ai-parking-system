import React, { createContext, useContext, useReducer } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const BookingContext = createContext();

const initialState = {
  availableSlots: [],
  currentBooking: null,
  userBookings: [],
  loading: false,
  error: null
};

const bookingReducer = (state, action) => {
  switch (action.type) {
    case 'SET_LOADING':
      return {
        ...state,
        loading: action.payload
      };
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
        loading: false
      };
    case 'SET_AVAILABLE_SLOTS':
      return {
        ...state,
        availableSlots: action.payload,
        loading: false,
        error: null
      };
    case 'SET_CURRENT_BOOKING':
      return {
        ...state,
        currentBooking: action.payload,
        loading: false,
        error: null
      };
    case 'SET_USER_BOOKINGS':
      return {
        ...state,
        userBookings: action.payload,
        loading: false,
        error: null
      };
    case 'ADD_BOOKING':
      return {
        ...state,
        userBookings: [action.payload, ...state.userBookings],
        currentBooking: null,
        loading: false,
        error: null
      };
    case 'UPDATE_BOOKING':
      return {
        ...state,
        userBookings: state.userBookings.map(booking =>
          booking._id === action.payload._id ? action.payload : booking
        ),
        loading: false,
        error: null
      };
    case 'CLEAR_CURRENT_BOOKING':
      return {
        ...state,
        currentBooking: null
      };
    default:
      return state;
  }
};

export const BookingProvider = ({ children }) => {
  const [state, dispatch] = useReducer(bookingReducer, initialState);

  // Get available slots
  const getAvailableSlots = async (date, startTime, endTime) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const res = await axios.get('/api/bookings/available-slots', {
        params: { date, startTime, endTime }
      });
      dispatch({ type: 'SET_AVAILABLE_SLOTS', payload: res.data.data });
      return res.data.data;
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to get available slots';
      dispatch({ type: 'SET_ERROR', payload: message });
      toast.error(message);
      return null;
    }
  };

  // Create booking
  const createBooking = async (bookingData) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const res = await axios.post('/api/bookings', bookingData);
      dispatch({ type: 'ADD_BOOKING', payload: res.data.data });
      toast.success('Booking created successfully!');
      return { success: true, booking: res.data.data };
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to create booking';
      dispatch({ type: 'SET_ERROR', payload: message });
      toast.error(message);
      return { success: false, message };
    }
  };

  // Get user bookings
  const getUserBookings = async (page = 1, limit = 10, status = null) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const params = { page, limit };
      if (status) params.status = status;
      
      const res = await axios.get('/api/bookings/my-bookings', { params });
      dispatch({ type: 'SET_USER_BOOKINGS', payload: res.data.data.bookings });
      return res.data.data;
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to get bookings';
      dispatch({ type: 'SET_ERROR', payload: message });
      toast.error(message);
      return null;
    }
  };

  // Get booking by ID
  const getBookingById = async (bookingId) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const res = await axios.get(`/api/bookings/${bookingId}`);
      dispatch({ type: 'SET_CURRENT_BOOKING', payload: res.data.data });
      return res.data.data;
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to get booking';
      dispatch({ type: 'SET_ERROR', payload: message });
      toast.error(message);
      return null;
    }
  };

  // Cancel booking
  const cancelBooking = async (bookingId) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const res = await axios.put(`/api/bookings/${bookingId}/cancel`);
      dispatch({ type: 'UPDATE_BOOKING', payload: res.data.data });
      toast.success('Booking cancelled successfully!');
      return { success: true };
    } catch (error) {
      const message = error.response?.data?.message || 'Failed to cancel booking';
      dispatch({ type: 'SET_ERROR', payload: message });
      toast.error(message);
      return { success: false, message };
    }
  };

  // Calculate booking price
  const calculatePrice = (startTime, endTime) => {
    const start = new Date(`2000-01-01T${startTime}`);
    const end = new Date(`2000-01-01T${endTime}`);
    const hours = (end - start) / (1000 * 60 * 60);
    
    // Base rate: LKR 500 per hour (Basic package)
    const baseRate = 500;
    const total = Math.ceil(hours) * baseRate;
    
    return Math.max(total, 500); // Minimum LKR 500
  };

  // Clear current booking
  const clearCurrentBooking = () => {
    dispatch({ type: 'CLEAR_CURRENT_BOOKING' });
  };

  const value = {
    availableSlots: state.availableSlots,
    currentBooking: state.currentBooking,
    userBookings: state.userBookings,
    loading: state.loading,
    error: state.error,
    getAvailableSlots,
    createBooking,
    getUserBookings,
    getBookingById,
    cancelBooking,
    calculatePrice,
    clearCurrentBooking
  };

  return (
    <BookingContext.Provider value={value}>
      {children}
    </BookingContext.Provider>
  );
};

export const useBooking = () => {
  const context = useContext(BookingContext);
  if (!context) {
    throw new Error('useBooking must be used within a BookingProvider');
  }
  return context;
}; 