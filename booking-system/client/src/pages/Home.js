import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Home = () => {
  const { isAuthenticated } = useAuth();

  return (
    <div>
      {/* Modern Hero Section - Inspired by Parkivia */}
      <section className="hero" style={{
        background: 'linear-gradient(135deg, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.5) 100%), url("https://media.gq-magazine.co.uk/photos/5dc3f0d643196300087c91bf/16:9/w_2560%2Cc_limit/Rolls-Royce-landscape-1-711.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Overlay Pattern */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.3) 0%, transparent 50%)',
          zIndex: 1
        }}></div>

        <div className="hero-content" style={{ position: 'relative', zIndex: 2 }}>
          <div className="container">
                         <div style={{ 
               display: 'flex',
               flexDirection: 'column',
               alignItems: 'center',
               justifyContent: 'center',
               textAlign: 'center',
               maxWidth: '1200px',
               margin: '0 auto',
               minHeight: '80vh',
               padding: 'var(--spacing-3xl) 0'
             }}>
                               {/* Main Title */}
                <h1 className="hero-title" style={{ 
                  color: '#ffffff',
                  fontSize: 'clamp(2.5rem, 8vw, 5rem)',
                  fontWeight: '900',
                  margin: '0 0 var(--spacing-xl) 0',
                  letterSpacing: '-0.02em',
                  lineHeight: '1.1',
                  animation: 'fadeInDown 1s ease-out',
                  fontFamily: '"Lexend", sans-serif',
                  fontOpticalSizing: 'auto',
                  fontStyle: 'normal'
                }}>
                  YOU CAN'T PARK CLOSER
                </h1>

               {/* Subtitle */}
               <p className="hero-subtitle" style={{ 
                 color: '#ffffff', 
                 fontSize: 'clamp(1.1rem, 4vw, 1.5rem)',
                 margin: '0 0 var(--spacing-3xl) 0',
                 lineHeight: '1.6',
                 animation: 'fadeInUp 1s ease-out 0.3s both',
                 fontWeight: '400',
                 maxWidth: '800px'
               }}>
                 Instantly book your space today. Trusted by millions at University of Moratuwa.
               </p>

               {/* CTA Buttons */}
               <div style={{ 
                 display: 'flex', 
                 gap: 'var(--spacing-lg)', 
                 flexWrap: 'wrap',
                 justifyContent: 'center',
                 animation: 'fadeInUp 1s ease-out 0.6s both'
               }}>
                 {isAuthenticated ? (
                   <Link to="/book" className="btn" style={{
                     padding: 'var(--spacing-xl) var(--spacing-3xl)',
                     fontSize: 'clamp(1rem, 3vw, 1.3rem)',
                     fontWeight: '700',
                     borderRadius: 'var(--radius-2xl)',
                     boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                     transition: 'all 0.3s ease',
                     textDecoration: 'none',
                     display: 'inline-block',
                     minWidth: '220px',
                     background: 'linear-gradient(135deg, var(--uom-primary) 0%, #8B0000 100%)',
                     color: 'white',
                     border: 'none',
                     textAlign: 'center'
                   }}>
                     Book Your Space
                   </Link>
                 ) : (
                   <>
                     <Link to="/register" className="btn btn-gold" style={{
                       padding: 'var(--spacing-xl) var(--spacing-3xl)',
                       fontSize: 'clamp(1rem, 3vw, 1.3rem)',
                       fontWeight: '700',
                       borderRadius: 'var(--radius-2xl)',
                       boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                       transition: 'all 0.3s ease',
                       textDecoration: 'none',
                       display: 'inline-block',
                       minWidth: '220px',
                       background: 'linear-gradient(135deg, var(--uom-gold) 0%, #FFD700 100%)',
                       color: 'var(--gray-900)',
                       textAlign: 'center'
                     }}>
                       Get Started Now
                     </Link>
                     <Link to="/login" className="btn btn-outline" style={{ 
                       color: 'white', 
                       borderColor: 'white',
                       padding: 'var(--spacing-xl) var(--spacing-3xl)',
                       fontSize: 'clamp(1rem, 3vw, 1.3rem)',
                       fontWeight: '600',
                       borderRadius: 'var(--radius-2xl)',
                       border: '3px solid white',
                       textDecoration: 'none',
                       display: 'inline-block',
                       transition: 'all 0.3s ease',
                       background: 'rgba(255,255,255,0.1)',
                       backdropFilter: 'blur(20px)',
                       minWidth: '220px',
                       textAlign: 'center'
                     }}>
                       Sign In
                     </Link>
                   </>
                 )}
               </div>

               {/* Trust Indicators */}
               <div style={{
                 display: 'flex',
                 gap: 'var(--spacing-xl)',
                 marginTop: 'var(--spacing-2xl)',
                 animation: 'fadeInUp 1s ease-out 0.9s both',
                 flexWrap: 'wrap',
                 justifyContent: 'center'
               }}>
                 <div style={{
                   display: 'flex',
                   alignItems: 'center',
                   gap: 'var(--spacing-sm)',
                   color: '#ffffff',
                   fontSize: 'clamp(0.8rem, 2.5vw, 0.9rem)'
                 }}>
                   <span style={{ fontSize: '1.2rem' }}>⭐</span>
                   <span>5-Star Rated</span>
                 </div>
                 <div style={{
                   display: 'flex',
                   alignItems: 'center',
                   gap: 'var(--spacing-sm)',
                   color: '#ffffff',
                   fontSize: 'clamp(0.8rem, 2.5vw, 0.9rem)'
                 }}>
                   <span style={{ fontSize: '1.2rem' }}>🔒</span>
                   <span>Secure & Safe</span>
                 </div>
                 <div style={{
                   display: 'flex',
                   alignItems: 'center',
                   gap: 'var(--spacing-sm)',
                   color: '#ffffff',
                   fontSize: 'clamp(0.8rem, 2.5vw, 0.9rem)'
                 }}>
                   <span style={{ fontSize: '1.2rem' }}>⚡</span>
                   <span>Instant Booking</span>
                 </div>
               </div>
             </div>

            {/* Quick Booking Bar */}
            <div style={{
              background: 'rgba(255,255,255,0.95)',
              borderRadius: 'var(--radius-2xl)',
              padding: 'var(--spacing-xl)',
              marginTop: 'var(--spacing-3xl)',
              boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
              backdropFilter: 'blur(20px)',
              animation: 'fadeInUp 1s ease-out 1.2s both'
            }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 'var(--spacing-lg)',
                alignItems: 'center'
              }}>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '0.9rem', 
                    fontWeight: '600', 
                    color: 'var(--gray-700)',
                    marginBottom: 'var(--spacing-xs)'
                  }}>
                    Select Car Park
                  </label>
                  <select style={{
                    width: '100%',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-lg)',
                    border: '2px solid var(--gray-200)',
                    fontSize: '1rem',
                    background: 'white'
                  }}>
                    <option>Main Campus Parking</option>
                    <option>Engineering Faculty</option>
                    <option>Library Parking</option>
                  </select>
                </div>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '0.9rem', 
                    fontWeight: '600', 
                    color: 'var(--gray-700)',
                    marginBottom: 'var(--spacing-xs)'
                  }}>
                    Your Name
                  </label>
                  <input type="text" placeholder="Enter your name" style={{
                    width: '100%',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-lg)',
                    border: '2px solid var(--gray-200)',
                    fontSize: '1rem'
                  }} />
                </div>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '0.9rem', 
                    fontWeight: '600', 
                    color: 'var(--gray-700)',
                    marginBottom: 'var(--spacing-xs)'
                  }}>
                    Your Phone Number
                  </label>
                  <input type="tel" placeholder="Enter phone number" style={{
                    width: '100%',
                    padding: 'var(--spacing-md)',
                    borderRadius: 'var(--radius-lg)',
                    border: '2px solid var(--gray-200)',
                    fontSize: '1rem'
                  }} />
                </div>
                <div style={{ alignSelf: 'end' }}>
                  <Link to="/book" className="btn" style={{
                    width: '100%',
                    padding: 'var(--spacing-lg)',
                    fontSize: '1.1rem',
                    fontWeight: '700',
                    borderRadius: 'var(--radius-lg)',
                    background: 'linear-gradient(135deg, var(--uom-primary) 0%, #8B0000 100%)',
                    color: 'white',
                    textDecoration: 'none',
                    textAlign: 'center',
                    display: 'block',
                    transition: 'all 0.3s ease'
                  }}>
                    Book Now
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Enhanced Features Section */}
      <section style={{ padding: 'var(--spacing-3xl) 0', background: 'white' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 'var(--spacing-3xl)' }}>
            <h2 style={{ 
              fontSize: '3rem', 
              fontWeight: '800', 
              marginBottom: 'var(--spacing-lg)',
              color: 'var(--uom-primary)',
              textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
            }}>
              Why Choose AI Smart Parking System?
            </h2>
            <p style={{
              fontSize: '1.25rem',
              color: 'var(--gray-600)',
              maxWidth: '800px',
              margin: '0 auto',
              lineHeight: '1.6'
            }}>
              Experience cutting-edge technology combined with the prestige of University of Moratuwa
            </p>
          </div>
          
          <div className="grid grid-cols-3" style={{ gap: 'var(--spacing-xl)' }}>
            <div className="card animate-fade-in-up" style={{ 
              textAlign: 'center',
              padding: 'var(--spacing-2xl)',
              border: 'none',
              background: 'linear-gradient(135deg, var(--gray-50) 0%, white 100%)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '4px',
                background: 'var(--gradient-primary)'
              }}></div>
              <div style={{ 
                fontSize: '4rem', 
                marginBottom: 'var(--spacing-lg)',
                animation: 'pulse 2s infinite'
              }}>🚗</div>
              <h3 style={{ 
                fontSize: '1.75rem', 
                fontWeight: '700', 
                marginBottom: 'var(--spacing-lg)',
                color: 'var(--uom-primary)'
              }}>
                Easy Booking
              </h3>
              <p style={{ 
                color: 'var(--gray-600)', 
                lineHeight: '1.7',
                fontSize: '1.1rem'
              }}>
                Book your parking slot in advance with our simple and intuitive booking system. 
                No more circling around looking for parking!
              </p>
            </div>
            
            <div className="card animate-fade-in-up" style={{ 
              textAlign: 'center',
              padding: 'var(--spacing-2xl)',
              border: 'none',
              background: 'linear-gradient(135deg, var(--gray-50) 0%, white 100%)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '4px',
                background: 'var(--gradient-primary)'
              }}></div>
              <div style={{ 
                fontSize: '4rem', 
                marginBottom: 'var(--spacing-lg)',
                animation: 'pulse 2s infinite 0.5s'
              }}>💳</div>
              <h3 style={{ 
                fontSize: '1.75rem', 
                fontWeight: '700', 
                marginBottom: 'var(--spacing-lg)',
                color: 'var(--uom-primary)'
              }}>
                Secure Payment
              </h3>
              <p style={{ 
                color: 'var(--gray-600)', 
                lineHeight: '1.7',
                fontSize: '1.1rem'
              }}>
                Pay securely online with Stripe integration. No cash needed, 
                and all transactions are encrypted and protected.
              </p>
            </div>
            
            <div className="card animate-fade-in-up" style={{ 
              textAlign: 'center',
              padding: 'var(--spacing-2xl)',
              border: 'none',
              background: 'linear-gradient(135deg, var(--gray-50) 0%, white 100%)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '4px',
                background: 'var(--gradient-primary)'
              }}></div>
              <div style={{ 
                fontSize: '4rem', 
                marginBottom: 'var(--spacing-lg)',
                animation: 'pulse 2s infinite 1s'
              }}>📱</div>
              <h3 style={{ 
                fontSize: '1.75rem', 
                fontWeight: '700', 
                marginBottom: 'var(--spacing-lg)',
                color: 'var(--uom-primary)'
              }}>
                Mobile Friendly
              </h3>
              <p style={{ 
                color: 'var(--gray-600)', 
                lineHeight: '1.7',
                fontSize: '1.1rem'
              }}>
                Access your bookings and manage your account from any device. 
                Perfect for students and staff on the go.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Enhanced How It Works Section */}
      <section style={{ 
        padding: 'var(--spacing-3xl) 0', 
        background: 'linear-gradient(135deg, var(--gray-50) 0%, var(--gray-100) 100%)',
        position: 'relative'
      }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 'var(--spacing-3xl)' }}>
            <h2 style={{ 
              fontSize: '3rem', 
              fontWeight: '800', 
              marginBottom: 'var(--spacing-lg)',
              color: 'var(--uom-primary)',
              textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
            }}>
              How It Works
            </h2>
            <p style={{
              fontSize: '1.25rem',
              color: 'var(--gray-600)',
              maxWidth: '800px',
              margin: '0 auto',
              lineHeight: '1.6'
            }}>
              Simple steps to secure your parking spot at University of Moratuwa
            </p>
          </div>
          
          <div className="grid grid-cols-4" style={{ gap: 'var(--spacing-xl)' }}>
            {[
              { step: 1, icon: '📅', title: 'Choose Your Time', desc: 'Select your preferred date and time slot' },
              { step: 2, icon: '🚗', title: 'Enter Details', desc: 'Provide your vehicle and contact information' },
              { step: 3, icon: '💳', title: 'Pay & Confirm', desc: 'Complete secure payment and get instant confirmation' },
              { step: 4, icon: '✅', title: 'Park & Enjoy', desc: 'Arrive at your reserved slot and park hassle-free' }
            ].map((item, index) => (
                             <div key={item.step} style={{ textAlign: 'center', animationDelay: `${index * 0.2}s` }} className={`animate-fade-in-up`}>
                <div style={{ 
                  width: '80px', 
                  height: '80px', 
                  borderRadius: '50%', 
                  background: 'var(--gradient-primary)', 
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '2rem',
                  fontWeight: 'bold',
                  margin: '0 auto var(--spacing-lg)',
                  boxShadow: 'var(--shadow-lg)',
                  position: 'relative'
                }}>
                  {item.icon}
                  <div style={{
                    position: 'absolute',
                    top: '-5px',
                    right: '-5px',
                    width: '30px',
                    height: '30px',
                    borderRadius: '50%',
                    background: 'var(--uom-gold)',
                    color: 'var(--gray-900)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.875rem',
                    fontWeight: '700'
                  }}>
                    {item.step}
                  </div>
                </div>
                <h3 style={{ 
                  fontSize: '1.5rem', 
                  fontWeight: '700', 
                  marginBottom: 'var(--spacing-md)',
                  color: 'var(--uom-primary)'
                }}>
                  {item.title}
                </h3>
                <p style={{ 
                  color: 'var(--gray-600)',
                  lineHeight: '1.6',
                  fontSize: '1rem'
                }}>
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Enhanced Pricing Section */}
      <section style={{ padding: 'var(--spacing-3xl) 0', background: 'white' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: 'var(--spacing-3xl)' }}>
            <h2 style={{ 
              fontSize: '3rem', 
              fontWeight: '800', 
              marginBottom: 'var(--spacing-lg)',
              color: 'var(--uom-primary)',
              textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
            }}>
              Professional Pricing
            </h2>
            <p style={{
              fontSize: '1.25rem',
              color: 'var(--gray-600)',
              maxWidth: '800px',
              margin: '0 auto',
              lineHeight: '1.6'
            }}>
              Affordable rates for University of Moratuwa students, staff, and visitors
            </p>
          </div>
          
                     <div className="grid grid-cols-3" style={{ gap: 'var(--spacing-xl)', alignItems: 'stretch' }}>
             {/* Basic Package */}
             <div className="card animate-slide-in-left" style={{ 
               textAlign: 'center', 
               padding: 'var(--spacing-2xl)', 
               border: '3px solid var(--gray-200)',
               background: 'linear-gradient(135deg, white 0%, var(--gray-50) 100%)',
               position: 'relative',
               height: '100%',
               display: 'flex',
               flexDirection: 'column',
               justifyContent: 'space-between'
             }}>
              <h3 style={{ 
                fontSize: '2rem', 
                fontWeight: '800', 
                marginBottom: 'var(--spacing-lg)', 
                color: 'var(--uom-primary)'
              }}>
                Basic
              </h3>
              <div style={{ 
                fontSize: '3rem', 
                fontWeight: '900', 
                marginBottom: 'var(--spacing-sm)', 
                color: 'var(--uom-primary)',
                textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
              }}>
                LKR 500
              </div>
              <p style={{ 
                color: 'var(--gray-500)', 
                marginBottom: 'var(--spacing-xl)',
                fontSize: '1.1rem',
                fontWeight: '600'
              }}>per hour</p>
              <ul style={{ 
                textAlign: 'left', 
                listStyle: 'none', 
                padding: 0,
                marginBottom: 'var(--spacing-2xl)'
              }}>
                {[
                  'Minimum 1 hour booking',
                  'Standard parking slot',
                  'Basic security',
                  'Email confirmation'
                ].map((feature, index) => (
                  <li key={index} style={{ 
                    marginBottom: 'var(--spacing-md)', 
                    display: 'flex', 
                    alignItems: 'center',
                    fontSize: '1rem'
                  }}>
                    <span style={{ 
                      color: 'var(--success-600)', 
                      marginRight: 'var(--spacing-sm)',
                      fontSize: '1.2rem'
                    }}>✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              {isAuthenticated ? (
                <Link to="/book" className="btn btn-primary" style={{ width: '100%', fontSize: '1.1rem' }}>
                  Book Basic
                </Link>
              ) : (
                <Link to="/register" className="btn btn-primary" style={{ width: '100%', fontSize: '1.1rem' }}>
                  Get Started
                </Link>
              )}
            </div>

                         {/* Premium Package */}
             <div className="card animate-fade-in-up" style={{ 
               textAlign: 'center', 
               padding: 'var(--spacing-2xl)', 
               border: '3px solid var(--uom-primary)',
               background: 'linear-gradient(135deg, var(--primary-50) 0%, white 100%)',
               position: 'relative',
               height: '100%',
               display: 'flex',
               flexDirection: 'column',
               justifyContent: 'space-between'
             }}>
                               <div style={{
                  position: 'absolute',
                  top: '-8px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  background: 'var(--uom-primary)',
                  color: 'white',
                  padding: 'var(--spacing-xs) var(--spacing-lg)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.75rem',
                  fontWeight: '500',
                  boxShadow: 'var(--shadow-sm)',
                  zIndex: 10,
                  letterSpacing: '0.02em',
                  textTransform: 'uppercase'
                }}>
                  Popular
                </div>
              <h3 style={{ 
                fontSize: '2rem', 
                fontWeight: '800', 
                marginBottom: 'var(--spacing-lg)', 
                color: 'var(--uom-primary)'
              }}>
                Premium
              </h3>
              <div style={{ 
                fontSize: '3rem', 
                fontWeight: '900', 
                marginBottom: 'var(--spacing-sm)', 
                color: 'var(--uom-primary)',
                textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
              }}>
                LKR 750
              </div>
              <p style={{ 
                color: 'var(--gray-500)', 
                marginBottom: 'var(--spacing-xl)',
                fontSize: '1.1rem',
                fontWeight: '600'
              }}>per hour</p>
              <ul style={{ 
                textAlign: 'left', 
                listStyle: 'none', 
                padding: 0,
                marginBottom: 'var(--spacing-2xl)'
              }}>
                {[
                  'All Basic features',
                  'Priority parking slot',
                  'Enhanced security',
                  'SMS notifications',
                  'Free cancellation (3 hours)'
                ].map((feature, index) => (
                  <li key={index} style={{ 
                    marginBottom: 'var(--spacing-md)', 
                    display: 'flex', 
                    alignItems: 'center',
                    fontSize: '1rem'
                  }}>
                    <span style={{ 
                      color: 'var(--success-600)', 
                      marginRight: 'var(--spacing-sm)',
                      fontSize: '1.2rem'
                    }}>✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              {isAuthenticated ? (
                <Link to="/book" className="btn btn-gold" style={{ width: '100%', fontSize: '1.1rem' }}>
                  Book Premium
                </Link>
              ) : (
                <Link to="/register" className="btn btn-gold" style={{ width: '100%', fontSize: '1.1rem' }}>
                  Get Started
                </Link>
              )}
            </div>

                         {/* VIP Package */}
             <div className="card animate-slide-in-right" style={{ 
               textAlign: 'center', 
               padding: 'var(--spacing-2xl)', 
               border: '3px solid var(--gray-200)',
               background: 'linear-gradient(135deg, white 0%, var(--gray-50) 100%)',
               position: 'relative',
               height: '100%',
               display: 'flex',
               flexDirection: 'column',
               justifyContent: 'space-between'
             }}>
              <h3 style={{ 
                fontSize: '2rem', 
                fontWeight: '800', 
                marginBottom: 'var(--spacing-lg)', 
                color: 'var(--uom-primary)'
              }}>
                VIP
              </h3>
              <div style={{ 
                fontSize: '3rem', 
                fontWeight: '900', 
                marginBottom: 'var(--spacing-sm)', 
                color: 'var(--uom-primary)',
                textShadow: '2px 2px 4px rgba(0,0,0,0.1)'
              }}>
                LKR 1,200
              </div>
              <p style={{ 
                color: 'var(--gray-500)', 
                marginBottom: 'var(--spacing-xl)',
                fontSize: '1.1rem',
                fontWeight: '600'
              }}>per hour</p>
              <ul style={{ 
                textAlign: 'left', 
                listStyle: 'none', 
                padding: 0,
                marginBottom: 'var(--spacing-2xl)'
              }}>
                {[
                  'All Premium features',
                  'Reserved VIP parking',
                  '24/7 security monitoring',
                  'Priority customer support',
                  'Free cancellation (6 hours)',
                  'Valet service available'
                ].map((feature, index) => (
                  <li key={index} style={{ 
                    marginBottom: 'var(--spacing-md)', 
                    display: 'flex', 
                    alignItems: 'center',
                    fontSize: '1rem'
                  }}>
                    <span style={{ 
                      color: 'var(--success-600)', 
                      marginRight: 'var(--spacing-sm)',
                      fontSize: '1.2rem'
                    }}>✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              {isAuthenticated ? (
                <Link to="/book" className="btn btn-primary" style={{ width: '100%', fontSize: '1.1rem' }}>
                  Book VIP
                </Link>
              ) : (
                <Link to="/register" className="btn btn-primary" style={{ width: '100%', fontSize: '1.1rem' }}>
                  Get Started
                </Link>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Enhanced Footer */}
      <footer className="footer">
        <div className="container">
          <div className="footer-content">
            
            
            <div className="footer-links">
              <a href="https://uom.lk" className="footer-link" target="_blank" rel="noopener noreferrer">
                University Website
              </a>
              <a href="https://uom.lk/cites/support-services" className="footer-link" target="_blank" rel="noopener noreferrer">
                IT Support
              </a>
              <a href="#" className="footer-link">
                Contact Us
              </a>
              <a href="#" className="footer-link">
                Privacy Policy
              </a>
            </div>
            
            <p style={{ 
              margin: 'var(--spacing-lg) 0 0 0',
              color: 'var(--gray-300)',
              fontSize: '0.875rem'
            }}>
              &copy; 2024 AI Smart Parking System - University of Moratuwa. All rights reserved.
            </p>
            <p style={{ 
              margin: 'var(--spacing-sm) 0 0 0', 
              fontSize: '0.75rem', 
              opacity: '0.8',
              color: 'var(--gray-400)'
            }}>
              Powered by <strong>Ryzera Technologies Pvt Ltd</strong>
            </p>
          </div>
        </div>
      </footer>

             {/* Enhanced CSS Animations */}
       <style>{`
         @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@100..900&display=swap');
         
         @keyframes shimmer {
           0% { transform: translateX(-100%); }
           100% { transform: translateX(100%); }
         }
        
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
        }
        
        @keyframes fadeInDown {
          from {
            opacity: 0;
            transform: translateY(-30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes slideInLeft {
          from {
            opacity: 0;
            transform: translateX(-30px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        
        @keyframes slideInRight {
          from {
            opacity: 0;
            transform: translateX(30px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
        
        .btn:hover {
          transform: translateY(-3px);
          box-shadow: var(--shadow-xl) !important;
        }
        
        .card:hover {
          transform: translateY(-8px) scale(1.02);
          box-shadow: var(--shadow-xl);
        }
      `}</style>
    </div>
  );
};

export default Home; 