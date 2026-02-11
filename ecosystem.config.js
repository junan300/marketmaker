// PM2 Ecosystem Configuration for 99% Uptime
// Install PM2: npm install -g pm2
// Start: pm2 start ecosystem.config.js
// Status: pm2 status
// Logs: pm2 logs
// Stop: pm2 stop all

module.exports = {
  apps: [
    {
      name: 'marketmaker-backend',
      script: 'python',
      args: '-m uvicorn backend.main:app --host 0.0.0.0 --port 8000',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
      },
      error_file: './logs/backend-error.log',
      out_file: './logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
    },
    {
      name: 'marketmaker-frontend',
      script: 'npm',
      args: 'run dev',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        NODE_ENV: 'production',
      },
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
    },
  ],
}
