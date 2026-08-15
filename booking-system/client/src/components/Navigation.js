import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Navigation = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/');
    setIsMenuOpen(false);
  };

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <>
      <nav className="nav">
        <div className="container nav-container">
          <Link to="/" className="nav-brand">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <img 
                  src="https://upload.wikimedia.org/wikipedia/en/thumb/6/60/University_of_Moratuwa_logo.png/220px-University_of_Moratuwa_logo.png" 
                  alt="University of Moratuwa Logo" 
                  style={{ 
                    width: '40px', 
                    height: '40px',
                    borderRadius: '50%',
                    objectFit: 'cover'
                  }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ 
                  fontSize: '15px', 
                  fontWeight: '800', 
                  color: 'var(--uom-primary)',
                  textShadow: '1px 1px 2px rgba(0,0,0,0.1)'
                }}>
                  AI SMART PARKING SYSTEM
                </span>
                <span style={{ 
                  fontSize: '12px', 
                  color: 'var(--gray-500)',
                  fontWeight: '500',
                  letterSpacing: '0.5px'
                }}>
                  University of Moratuwa
                </span>
              </div>
            </div>
          </Link>

          {/* Desktop Menu */}
          <ul className="nav-menu">
            <li>
              <Link 
                to="/" 
                className={`nav-link ${isActive('/') ? 'active' : ''}`}
              >
                Home
              </Link>
            </li>
            
            {isAuthenticated ? (
              <>
                <li>
                  <Link 
                    to="/book" 
                    className={`nav-link ${isActive('/book') ? 'active' : ''}`}
                  >
                    Book Now
                  </Link>
                </li>
                <li>
                  <Link 
                    to="/my-bookings" 
                    className={`nav-link ${isActive('/my-bookings') ? 'active' : ''}`}
                  >
                    My Bookings
                  </Link>
                </li>
                {user?.role === 'admin' && (
                  <li>
                    <Link 
                      to="/admin" 
                      className={`nav-link ${isActive('/admin') ? 'active' : ''}`}
                    >
                      Admin
                    </Link>
                  </li>
                )}
                <li>
                  <Link 
                    to="/profile" 
                    className={`nav-link ${isActive('/profile') ? 'active' : ''}`}
                  >
                    Profile
                  </Link>
                </li>
                <li>
                  <button 
                    onClick={handleLogout}
                    className="nav-link"
                    style={{ 
                      background: 'none', 
                      border: 'none', 
                      cursor: 'pointer',
                      color: 'var(--error-600)',
                      fontWeight: '600',
                      outline: 'none'
                    }}
                  >
                    Logout
                  </button>
                </li>
              </>
            ) : (
              <>
                <li>
                  <Link 
                    to="/login" 
                    className={`nav-link ${isActive('/login') ? 'active' : ''}`}
                  >
                    Login
                  </Link>
                </li>
                <li>
                  <Link 
                    to="/register" 
                    className={`nav-link ${isActive('/register') ? 'active' : ''}`}
                    style={{
                      background: 'var(--gradient-primary)',
                      color: 'white',
                      fontWeight: '700'
                    }}
                  >
                    Register
                  </Link>
                </li>
              </>
            )}
          </ul>

          {/* Mobile Menu Button */}
          <button 
            className="mobile-menu-btn"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            style={{
              display: 'none',
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              color: 'var(--uom-primary)',
              padding: 'var(--spacing-sm)',
              borderRadius: 'var(--radius-md)',
              transition: 'all 0.3s ease',
              outline: 'none'
            }}
          >
            {isMenuOpen ? '✕' : '☰'}
          </button>
        </div>
      </nav>

      {/* Enhanced Mobile Menu */}
      {isMenuOpen && (
        <div className="mobile-menu active">
          <div className="mobile-menu-content">
            <div style={{
              textAlign: 'center',
              marginBottom: 'var(--spacing-xl)',
              paddingBottom: 'var(--spacing-lg)',
              borderBottom: '2px solid var(--gray-100)'
            }}>
              <div style={{
                width: '80px',
                height: '80px',
                borderRadius: '50%',
                background: 'var(--gradient-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto var(--spacing-md)',
                boxShadow: 'var(--shadow-lg)'
              }}>
                <img 
                  src="https://upload.wikimedia.org/wikipedia/en/thumb/6/60/University_of_Moratuwa_logo.png/220px-University_of_Moratuwa_logo.png" 
                  alt="UoM Logo" 
                  style={{ 
                    width: '60px', 
                    height: '60px',
                    borderRadius: '50%',
                    objectFit: 'cover'
                  }}
                />
              </div>
              <h3 style={{
                color: 'var(--uom-primary)',
                margin: '0 0 var(--spacing-xs) 0',
                fontSize: '1.25rem',
                fontWeight: '700'
              }}>
                AI Smart Parking System
              </h3>
              <p style={{
                color: 'var(--gray-500)',
                margin: 0,
                fontSize: '0.875rem'
              }}>
                University of Moratuwa
              </p>
            </div>

            <ul style={{ 
              listStyle: 'none', 
              margin: 0, 
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--spacing-sm)'
            }}>
              <li>
                <Link 
                  to="/" 
                  className={`nav-link ${isActive('/') ? 'active' : ''}`}
                  onClick={() => setIsMenuOpen(false)}
                  style={{
                    display: 'block',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-lg)',
                    textDecoration: 'none',
                    transition: 'all 0.3s ease',
                    textAlign: 'center',
                    fontSize: '1rem',
                    fontWeight: '600',
                    outline: 'none'
                  }}
                >
                  Home
                </Link>
              </li>
              
              {isAuthenticated ? (
                <>
                  <li>
                    <Link 
                      to="/book" 
                      className={`nav-link ${isActive('/book') ? 'active' : ''}`}
                      onClick={() => setIsMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: 'var(--spacing-md)',
                        borderRadius: 'var(--radius-lg)',
                        textDecoration: 'none',
                        transition: 'all 0.3s ease',
                        textAlign: 'center',
                        fontSize: '1rem',
                        fontWeight: '600',
                        outline: 'none'
                      }}
                    >
                      Book Now
                    </Link>
                  </li>
                  <li>
                    <Link 
                      to="/my-bookings" 
                      className={`nav-link ${isActive('/my-bookings') ? 'active' : ''}`}
                      onClick={() => setIsMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: 'var(--spacing-md)',
                        borderRadius: 'var(--radius-lg)',
                        textDecoration: 'none',
                        transition: 'all 0.3s ease',
                        textAlign: 'center',
                        fontSize: '1rem',
                        fontWeight: '600',
                        outline: 'none'
                      }}
                    >
                      My Bookings
                    </Link>
                  </li>
                  {user?.role === 'admin' && (
                    <li>
                      <Link 
                        to="/admin" 
                        className={`nav-link ${isActive('/admin') ? 'active' : ''}`}
                        onClick={() => setIsMenuOpen(false)}
                        style={{
                          display: 'block',
                          padding: 'var(--spacing-md)',
                          borderRadius: 'var(--radius-lg)',
                          textDecoration: 'none',
                          transition: 'all 0.3s ease',
                          textAlign: 'center',
                          fontSize: '1rem',
                          fontWeight: '600',
                          outline: 'none'
                        }}
                      >
                        Admin Dashboard
                      </Link>
                    </li>
                  )}
                  <li>
                    <Link 
                      to="/profile" 
                      className={`nav-link ${isActive('/profile') ? 'active' : ''}`}
                      onClick={() => setIsMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: 'var(--spacing-md)',
                        borderRadius: 'var(--radius-lg)',
                        textDecoration: 'none',
                        transition: 'all 0.3s ease',
                        textAlign: 'center',
                        fontSize: '1rem',
                        fontWeight: '600',
                        outline: 'none'
                      }}
                    >
                      Profile
                    </Link>
                  </li>
                  <li>
                    <button 
                      onClick={handleLogout}
                      className="nav-link"
                      style={{ 
                        display: 'block',
                        width: '100%',
                        padding: 'var(--spacing-md)',
                        borderRadius: 'var(--radius-lg)',
                        textDecoration: 'none',
                        transition: 'all 0.3s ease',
                        textAlign: 'center',
                        fontSize: '1rem',
                        fontWeight: '600',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--error-600)',
                        outline: 'none'
                      }}
                    >
                      Logout
                    </button>
                  </li>
                </>
              ) : (
                <>
                  <li>
                    <Link 
                      to="/login" 
                      className={`nav-link ${isActive('/login') ? 'active' : ''}`}
                      onClick={() => setIsMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: 'var(--spacing-md)',
                        borderRadius: 'var(--radius-lg)',
                        textDecoration: 'none',
                        transition: 'all 0.3s ease',
                        textAlign: 'center',
                        fontSize: '1rem',
                        fontWeight: '600',
                        outline: 'none'
                      }}
                    >
                      Login
                    </Link>
                  </li>
                  <li>
                    <Link 
                      to="/register" 
                      className={`nav-link ${isActive('/register') ? 'active' : ''}`}
                      onClick={() => setIsMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: 'var(--spacing-md)',
                        borderRadius: 'var(--radius-lg)',
                        textDecoration: 'none',
                        transition: 'all 0.3s ease',
                        textAlign: 'center',
                        fontSize: '1rem',
                        fontWeight: '700',
                        background: 'var(--gradient-primary)',
                        color: 'white',
                        outline: 'none'
                      }}
                    >
                      Create Account
                    </Link>
                  </li>
                </>
              )}
            </ul>

            <div style={{
              marginTop: 'var(--spacing-xl)',
              paddingTop: 'var(--spacing-lg)',
              borderTop: '2px solid var(--gray-100)',
              textAlign: 'center'
            }}>
              <button
                onClick={() => setIsMenuOpen(false)}
                style={{
                  background: 'var(--gray-200)',
                  border: 'none',
                  padding: 'var(--spacing-sm) var(--spacing-lg)',
                  borderRadius: 'var(--radius-lg)',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  fontWeight: '600',
                  color: 'var(--gray-600)',
                  transition: 'all 0.3s ease',
                  outline: 'none'
                }}
              >
                Close Menu
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Navigation; 