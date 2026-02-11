# Market Maker Reliability Guide - 99% Uptime

This guide ensures your Market Maker runs reliably 24/7 with automatic recovery.

## Quick Start (Recommended)

### Option 1: PM2 Process Manager (Best for Production)

1. **Install PM2:**
   ```bash
   npm install -g pm2
   ```

2. **Start with PM2:**
   ```bash
   start-production.bat
   ```
   Or manually:
   ```bash
   pm2 start ecosystem.config.js
   ```

3. **Useful PM2 Commands:**
   ```bash
   pm2 status              # Check status
   pm2 logs                # View logs
   pm2 monit               # Monitor resources
   pm2 restart all         # Restart services
   pm2 stop all            # Stop services
   pm2 save                # Save current process list
   pm2 startup             # Auto-start on system boot
   ```

### Option 2: Windows Task Scheduler (Alternative)

1. Create a scheduled task that runs `start.bat` on system startup
2. Set it to restart on failure
3. Run health-check.py every minute as a separate task

## Features for Reliability

### ✅ Auto-Restart on Failure
- PM2 automatically restarts crashed processes
- Max 10 restarts with 4-second delay
- Memory limit protection (auto-restart at 500MB backend, 300M frontend)

### ✅ Health Monitoring
- Health check script: `health-check.py`
- Logs to `data/health-check.log`
- Can be scheduled to run every minute

### ✅ Logging
- Backend logs: `data/market_maker.log`
- PM2 logs: `logs/backend-out.log`, `logs/frontend-out.log`
- Health check logs: `data/health-check.log`

### ✅ Network Binding
- Backend: `0.0.0.0:8000` (accessible from network)
- Frontend: `0.0.0.0:3000` (accessible from network)
- Can access from other devices on your network

## Running Overnight / 24/7

### Setup Auto-Start on Boot

**Windows (PM2):**
```bash
pm2 startup
pm2 save
```

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "When the computer starts"
4. Action: Start a program
5. Program: `C:\path\to\start-production.bat`

### Monitor Remotely

1. **Access from other devices:**
   - Find your PC's IP: `ipconfig` (look for IPv4 Address)
   - Access: `http://YOUR_IP:3000`

2. **Set up port forwarding** (if accessing from internet):
   - Forward port 3000 to your PC
   - Use a domain or dynamic DNS service

### Health Check Setup

**Windows Task Scheduler:**
1. Create task to run `health-check.py` every minute
2. Use Python from your venv: `venv\Scripts\python.exe health-check.py`

**Or use PM2:**
```bash
pm2 start health-check.py --interpreter python --cron "*/1 * * * *"
```

## Troubleshooting

### Service Won't Start
- Check logs: `pm2 logs` or `data/market_maker.log`
- Verify Python dependencies: `pip install -r requirements.txt`
- Check .env file exists and has correct values

### Service Keeps Restarting
- Check memory usage: `pm2 monit`
- Review error logs for specific errors
- May need to increase memory limits in `ecosystem.config.js`

### Can't Access from Browser
- Check firewall allows ports 3000 and 8000
- Verify services are running: `pm2 status`
- Try `http://127.0.0.1:3000` instead of `localhost`

### Wallet Issues
- Ensure `MM_KEYSTORE_PASSPHRASE` is set in .env
- Check `data/wallets/` directory exists
- Review wallet logs in backend output

## Best Practices

1. **Regular Backups:**
   - Backup `data/wallets/keystore.enc` (encrypted wallet storage)
   - Backup `.env` file (keep secure!)
   - Backup `data/` directory regularly

2. **Monitoring:**
   - Check `pm2 status` daily
   - Review logs weekly
   - Set up alerts for critical errors

3. **Updates:**
   - Test updates on devnet first
   - Stop services before updating: `pm2 stop all`
   - Restart after updates: `pm2 restart all`

4. **Security:**
   - Change `MM_KEYSTORE_PASSPHRASE` to a strong password
   - Set `MM_API_KEY` for production
   - Use firewall rules for network access
   - Keep `.env` file secure (never commit to git)

## Performance Tips

- **Memory:** Monitor with `pm2 monit`, adjust limits if needed
- **CPU:** Market maker is lightweight, shouldn't use much CPU
- **Network:** Ensure stable internet for Solana RPC calls
- **Disk:** Logs can grow, rotate or clean old logs periodically

## Emergency Procedures

**If everything stops:**
1. Check `pm2 status` - are processes running?
2. Check logs: `pm2 logs --lines 100`
3. Restart: `pm2 restart all`
4. If still failing, check system resources (memory, disk space)

**If wallet issues:**
1. Verify keystore passphrase in .env
2. Check `data/wallets/keystore.enc` exists
3. Review backend logs for decryption errors

**If network issues:**
1. Test RPC endpoint: `curl http://localhost:8000/health`
2. Check Solana network status
3. Verify RPC_URL in .env is correct
