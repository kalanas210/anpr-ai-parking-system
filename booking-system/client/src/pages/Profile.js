import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const Profile = () => {
  const { user, updateProfile } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: user?.name || '',
    phone: user?.phone || ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.phone.trim()) {
      newErrors.phone = 'Phone number is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    
    try {
      const result = await updateProfile(formData);
      if (result.success) {
        setIsEditing(false);
      }
    } catch (error) {
      console.error('Update profile error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      name: user?.name || '',
      phone: user?.phone || ''
    });
    setErrors({});
    setIsEditing(false);
  };

  return (
    <div style={{ padding: '2rem 0' }}>
      <div className="container">
        <div style={{ maxWidth: '600px', margin: '0 auto' }}>
          <h1 style={{ fontSize: '2rem', fontWeight: '700', color: '#1f2937', marginBottom: '2rem' }}>
            Profile
          </h1>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Account Information</h2>
            </div>

            {isEditing ? (
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label htmlFor="name" className="form-label">Full Name</label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    className={`form-input ${errors.name ? 'error' : ''}`}
                    placeholder="Enter your full name"
                    disabled={isSubmitting}
                  />
                  {errors.name && <div className="error-message">{errors.name}</div>}
                </div>

                <div className="form-group">
                  <label htmlFor="email" className="form-label">Email Address</label>
                  <input
                    type="email"
                    id="email"
                    value={user?.email || ''}
                    className="form-input"
                    disabled
                    style={{ backgroundColor: '#f3f4f6' }}
                  />
                  <small style={{ color: '#6b7280', fontSize: '0.75rem' }}>
                    Email cannot be changed
                  </small>
                </div>

                <div className="form-group">
                  <label htmlFor="phone" className="form-label">Phone Number</label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                    className={`form-input ${errors.phone ? 'error' : ''}`}
                    placeholder="Enter your phone number"
                    disabled={isSubmitting}
                  />
                  {errors.phone && <div className="error-message">{errors.phone}</div>}
                </div>

                <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <div className="loading" style={{ marginRight: '0.5rem' }}></div>
                        Saving...
                      </>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="btn btn-secondary"
                    disabled={isSubmitting}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <div>
                <div className="grid grid-cols-2" style={{ gap: '1rem', marginBottom: '2rem' }}>
                  <div>
                    <label className="form-label">Full Name</label>
                    <p style={{ margin: 0, padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
                      {user?.name}
                    </p>
                  </div>
                  
                  <div>
                    <label className="form-label">Email Address</label>
                    <p style={{ margin: 0, padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
                      {user?.email}
                    </p>
                  </div>
                  
                  <div>
                    <label className="form-label">Phone Number</label>
                    <p style={{ margin: 0, padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
                      {user?.phone}
                    </p>
                  </div>
                  
                  <div>
                    <label className="form-label">Account Type</label>
                    <p style={{ margin: 0, padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
                      {user?.role === 'admin' ? 'Administrator' : 'User'}
                    </p>
                  </div>
                </div>

                <div>
                  <label className="form-label">Member Since</label>
                  <p style={{ margin: 0, padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
                    {new Date(user?.createdAt).toLocaleDateString()}
                  </p>
                </div>

                <div style={{ marginTop: '2rem' }}>
                  <button
                    onClick={() => setIsEditing(true)}
                    className="btn btn-primary"
                  >
                    Edit Profile
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile; 