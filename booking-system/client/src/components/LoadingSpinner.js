import React from 'react';

const LoadingSpinner = ({ size = 'medium', text = 'Loading...', variant = 'primary' }) => {
  const sizeClasses = {
    small: 'w-4 h-4',
    medium: 'w-8 h-8',
    large: 'w-12 h-12'
  };

  const getSpinnerStyle = () => {
    const baseStyle = {
      display: 'inline-block',
      borderRadius: '50%',
      border: '3px solid rgba(255, 255, 255, 0.3)',
      borderTopColor: 'white',
      animation: 'spin 1s ease-in-out infinite'
    };

    const sizes = {
      small: { width: '16px', height: '16px', borderWidth: '2px' },
      medium: { width: '32px', height: '32px', borderWidth: '3px' },
      large: { width: '48px', height: '48px', borderWidth: '4px' }
    };

    const variants = {
      primary: {
        borderTopColor: 'var(--uom-primary)',
        borderColor: 'rgba(123, 13, 13, 0.2)'
      },
      gold: {
        borderTopColor: 'var(--uom-gold)',
        borderColor: 'rgba(212, 175, 55, 0.2)'
      },
      white: {
        borderTopColor: 'white',
        borderColor: 'rgba(255, 255, 255, 0.3)'
      }
    };

    return {
      ...baseStyle,
      ...sizes[size],
      ...variants[variant]
    };
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      gap: 'var(--spacing-lg)',
      padding: 'var(--spacing-xl)'
    }}>
      {/* Enhanced Spinner */}
      <div style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        {/* Main Spinner */}
        <div style={getSpinnerStyle()}></div>
        
        {/* Pulsing Ring Effect */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: size === 'small' ? '24px' : size === 'large' ? '64px' : '48px',
          height: size === 'small' ? '24px' : size === 'large' ? '64px' : '48px',
          borderRadius: '50%',
          border: '2px solid var(--uom-primary)',
          opacity: 0.3,
          animation: 'pulse 2s infinite'
        }}></div>
        
        {/* Outer Ring */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: size === 'small' ? '32px' : size === 'large' ? '80px' : '64px',
          height: size === 'small' ? '32px' : size === 'large' ? '80px' : '64px',
          borderRadius: '50%',
          border: '1px solid var(--uom-secondary)',
          opacity: 0.2,
          animation: 'pulse 3s infinite 0.5s'
        }}></div>
      </div>

      {/* Loading Text */}
      {text && (
        <div style={{
          textAlign: 'center'
        }}>
          <p style={{
            color: variant === 'white' ? 'white' : 'var(--gray-600)',
            fontSize: size === 'small' ? '0.875rem' : size === 'large' ? '1.25rem' : '1rem',
            margin: 0,
            fontWeight: '600',
            textTransform: 'uppercase',
            letterSpacing: '0.05em'
          }}>
            {text}
          </p>
          
          {/* Animated Dots */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '4px',
            marginTop: 'var(--spacing-sm)'
          }}>
            {[0, 1, 2].map((index) => (
              <div
                key={index}
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: variant === 'white' ? 'white' : 'var(--uom-primary)',
                  animation: `bounce 1.4s infinite ease-in-out both`,
                  animationDelay: `${index * 0.16}s`
                }}
              ></div>
            ))}
          </div>
        </div>
      )}

      {/* Enhanced CSS Animations */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        @keyframes pulse {
          0%, 100% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 0.3;
          }
          50% {
            transform: translate(-50%, -50%) scale(1.1);
            opacity: 0.1;
          }
        }
        
        @keyframes bounce {
          0%, 80%, 100% {
            transform: scale(0);
          }
          40% {
            transform: scale(1);
          }
        }
      `}</style>
    </div>
  );
};

export default LoadingSpinner; 