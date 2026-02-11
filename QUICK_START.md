# Quick Start Guide - Market Maker

## 🚀 Starting the Application

### Development Mode (Testing)
```bash
# Terminal 1 - Backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 - Frontend  
npm run dev
```

### Production Mode (99% Uptime - Recommended)
```bash
# Install PM2 (one time)
npm install -g pm2

# Start with auto-restart
start-production.bat
```

Access: http://localhost:3000

## 🔐 Wallet Setup

### Create New Wallet
1. Click "Create New Wallet" button
2. Save your public key somewhere safe
3. Wallet is automatically encrypted and stored

### Import Existing Wallet
1. Click "Import Existing Wallet"
2. Paste your private key (supports multiple formats):
   - Base58 encoded
   - Hex format (with or without 0x)
   - Array format [1,2,3,...]
3. Click "Import Wallet"
4. Wallet is encrypted and stored securely

## 📊 Dashboard Overview

The dashboard shows everything at a glance:

- **Status Banner** (top): Shows if market maker is running, trade count, and balance
- **Account Panel**: Wallet address, balance, network
- **Control Panel**: Start/Stop market maker
- **Stats Panel**: Total trades, profit, uptime
- **Config Panel**: Trading settings (spread, order size, etc.)

## ⚙️ Configuration

### Environment Variables (.env file)

**Required:**
- `MM_KEYSTORE_PASSPHRASE` - Encryption password (CHANGE THIS!)
- `TOKEN_MINT` - Token address to market make

**Optional:**
- `SOLANA_NETWORK` - devnet or mainnet-beta (default: devnet)
- `RPC_URL` - Solana RPC endpoint
- `BASE_TRADE_SIZE_SOL` - Trade size (default: 0.1)
- `CYCLE_INTERVAL_S` - Check interval in seconds (default: 15)

### Trading Settings

Adjust in the Config Panel:
- **Spread Percentage**: Profit margin per trade
- **Order Size**: Amount of SOL per trade
- **Minimum Balance**: Stop trading if balance drops below this

## 🔄 Running 24/7

### Using PM2 (Recommended)

```bash
# Start
pm2 start ecosystem.config.js

# Check status
pm2 status

# View logs
pm2 logs

# Monitor resources
pm2 monit

# Auto-start on boot
pm2 startup
pm2 save
```

### Features:
- ✅ Auto-restart on crash
- ✅ Memory limit protection
- ✅ Logging to files
- ✅ Resource monitoring

## 📱 Access from Other Devices

1. Find your PC's IP address: `ipconfig` (Windows)
2. Access from phone/tablet: `http://YOUR_IP:3000`
3. Make sure firewall allows ports 3000 and 8000

## 🛠️ Troubleshooting

### Frontend shows nothing
- Check both servers are running: `pm2 status`
- Try `http://127.0.0.1:3000` instead of `localhost`
- Check browser console (F12) for errors

### Import wallet fails
- Verify private key format (try base58, hex, or array)
- Check backend logs: `pm2 logs marketmaker-backend`
- Ensure key is 32 or 64 bytes when decoded

### Service keeps restarting
- Check logs: `pm2 logs`
- Verify .env file has all required variables
- Check system resources: `pm2 monit`

### Can't access from browser
- Verify services are running: `pm2 status`
- Check firewall settings
- Try different browser or clear cache

## 📝 Important Notes

1. **Security**: Change `MM_KEYSTORE_PASSPHRASE` in .env to a strong password
2. **Backups**: Regularly backup `data/wallets/keystore.enc`
3. **Testing**: Always test on devnet first before mainnet
4. **Monitoring**: Check `pm2 status` regularly for health

## 📚 More Information

- Full reliability guide: `RELIABILITY_GUIDE.md`
- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health
