// Generates a server/.env file from placeholder values.
// Fill in your real credentials after running, or just copy .env.example to .env.
const fs = require('fs');
const path = require('path');

const envContent = `# Server Configuration
PORT=5001
NODE_ENV=development

# Allowed CORS origins (comma-separated) - the React client dev server
ALLOWED_ORIGINS=http://localhost:3000

# Database Configuration
MONGODB_URI=your_mongodb_connection_string

# JWT Configuration (use a long random string)
JWT_SECRET=change_me_to_a_long_random_secret

# Stripe Configuration (from your Stripe dashboard)
STRIPE_PUBLISH_KEY=your_stripe_publishable_key
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# SMS Gateway (ozonedesk) - optional
SMS_BASE_URL=http://sms.ozonedesk.com/api/v1/send.php
SMS_USER_ID=your_sms_user_id
SMS_API_KEY=your_sms_api_key
SMS_SENDER_ID=your_sms_sender_id

# Email Configuration (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
`;

const envPath = path.join(__dirname, '.env');

if (fs.existsSync(envPath)) {
  console.log('⚠️  .env already exists - not overwriting. Edit it manually if needed.');
  process.exit(0);
}

try {
  fs.writeFileSync(envPath, envContent);
  console.log('✅ server/.env created from placeholders.');
  console.log('🔧 Now open it and fill in your real MongoDB / JWT / Stripe credentials.');
} catch (error) {
  console.error('❌ Error creating .env file:', error.message);
}
