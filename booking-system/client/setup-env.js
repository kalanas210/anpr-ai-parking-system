// Generates a client/.env file from placeholder values.
// Fill in your real Stripe publishable key after running, or copy .env.example to .env.
const fs = require('fs');
const path = require('path');

const envContent = `# Client Configuration
REACT_APP_API_URL=http://localhost:5001/api
REACT_APP_STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key

# Development Configuration
REACT_APP_ENV=development
REACT_APP_DEBUG=true

# Feature Flags (optional)
REACT_APP_ENABLE_ANALYTICS=false
REACT_APP_ENABLE_NOTIFICATIONS=true
`;

const envPath = path.join(__dirname, '.env');

if (fs.existsSync(envPath)) {
  console.log('⚠️  .env already exists - not overwriting. Edit it manually if needed.');
  process.exit(0);
}

try {
  fs.writeFileSync(envPath, envContent);
  console.log('✅ client/.env created from placeholders.');
  console.log('🔧 Now open it and set REACT_APP_STRIPE_PUBLISHABLE_KEY to your Stripe key.');
} catch (error) {
  console.error('❌ Error creating client .env file:', error.message);
}
