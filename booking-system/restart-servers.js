const { spawn } = require('child_process');
const path = require('path');

console.log('🔄 Restarting servers...\n');

// Function to run a command
function runCommand(command, args, cwd, name) {
  return new Promise((resolve, reject) => {
    console.log(`🚀 Starting ${name}...`);
    
    const child = spawn(command, args, {
      cwd,
      stdio: 'inherit',
      shell: true
    });

    child.on('close', (code) => {
      if (code === 0) {
        console.log(`✅ ${name} stopped successfully`);
        resolve();
      } else {
        console.log(`❌ ${name} stopped with code ${code}`);
        reject(new Error(`${name} stopped with code ${code}`));
      }
    });

    child.on('error', (error) => {
      console.error(`❌ Error starting ${name}:`, error);
      reject(error);
    });
  });
}

// Instructions for manual restart
console.log('📋 Manual Restart Instructions:');
console.log('');
console.log('1. Stop your current server (Ctrl+C)');
console.log('2. Navigate to server directory: cd booking-system/server');
console.log('3. Start server: npm start');
console.log('4. In a new terminal, navigate to client: cd booking-system/client');
console.log('5. Start client: npm start');
console.log('');
console.log('🔧 After restart, test these endpoints:');
console.log('- http://localhost:5000/api/health');
console.log('- http://localhost:5000/api/test-auth');
console.log('');
console.log('💡 If you still get errors, check the server console for detailed logs.'); 