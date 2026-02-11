# Quick Setup Guide

## Environment Variables

Create a `.env` file in the root directory with these variables:

### For Devnet (Testing - Recommended)
```env
SOLANA_NETWORK=devnet
RPC_URL=https://api.devnet.solana.com
WALLET_PATH=./wallet.json
SPREAD_PERCENTAGE=0.5
ORDER_SIZE=0.1
MIN_BALANCE=1.0
API_HOST=0.0.0.0
API_PORT=8000
```

### For Mainnet (Production - Use with Caution!)
```env
SOLANA_NETWORK=mainnet-beta
RPC_URL=https://api.mainnet-beta.solana.com
WALLET_PATH=./wallet.json
SPREAD_PERCENTAGE=0.5
ORDER_SIZE=0.1
MIN_BALANCE=1.0
API_HOST=0.0.0.0
API_PORT=8000
```

## Step-by-Step Setup

### 1. Python Backend
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Node.js Frontend
```bash
# Install dependencies
npm install
```

### 3. Create .env File
Copy the environment variables above into a new `.env` file.

### 4. Start the Application

**Windows:**
```cmd
start.bat
```

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```

Or manually:
- Terminal 1: `python -m uvicorn backend.main:app --reload --port 8000`
- Terminal 2: `npm run dev`

### 5. Access the UI
Open browser to: `http://localhost:3000`

### 6. Create Wallet
- Click "Create New Wallet" in the UI
- Save your public key somewhere safe

### 7. Get Test SOL (Devnet Only)
- Visit: https://faucet.solana.com
- Paste your public key
- Request SOL

### 8. Start Trading!
- Configure your settings
- Click "Start Market Maker"
- Monitor your stats

## Verification Checklist

- [ ] Python 3.9+ installed
- [ ] Node.js 18+ installed
- [ ] Virtual environment created and activated
- [ ] Python dependencies installed (`pip install -r requirements.txt`)
- [ ] Node.js dependencies installed (`npm install`)
- [ ] `.env` file created with correct values
- [ ] Backend server starts without errors
- [ ] Frontend server starts without errors
- [ ] Can access UI at http://localhost:3000
- [ ] Wallet created successfully
- [ ] Have test SOL on devnet (if testing)

## Common Issues

**Port already in use:**
- Change `API_PORT` in `.env` (backend)
- Change port in `vite.config.ts` (frontend)

**Module not found errors:**
- Make sure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Wallet errors:**
- Check that `wallet.json` exists
- Try creating a new wallet through the UI
