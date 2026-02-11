# Solana Market Maker

A professional market making bot for Solana with a modern web UI.

## Features

- 🚀 Direct Solana blockchain integration
- 💹 Simple buy/sell market making logic
- 🖥️ Modern web UI for monitoring and control
- 🌐 Devnet/Mainnet switching
- 💻 Cross-platform support (Windows, Mac, Linux)
- 🔐 Secure wallet management

## Prerequisites

Before you begin, ensure you have:
- **Python 3.9+** installed ([Download](https://www.python.org/downloads/))
- **Node.js 18+** installed ([Download](https://nodejs.org/))
- A code editor (VS Code recommended)
- Internet connection

## Quick Start Guide

### Step 1: Clone/Download the Project

If you haven't already, make sure you're in the project directory:
```bash
cd marketmaker
```

### Step 2: Backend Setup

1. **Create a Python virtual environment:**
   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **Windows (CMD):**
     ```cmd
     venv\Scripts\activate.bat
     ```
   - **Mac/Linux:**
     ```bash
     source venv/bin/activate
     ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create environment configuration:**
   
   Create a `.env` file in the root directory with the following content:
   ```
   SOLANA_NETWORK=devnet
   RPC_URL=https://api.devnet.solana.com
   WALLET_PATH=./wallet.json
   SPREAD_PERCENTAGE=0.5
   ORDER_SIZE=0.1
   MIN_BALANCE=1.0
   API_HOST=0.0.0.0
   API_PORT=8000
   ```

### Step 3: Frontend Setup

1. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

### Step 4: Running the Application

You have two options:

#### Option A: Use the Startup Scripts (Recommended)

- **Windows:** Double-click `start.bat` or run:
  ```cmd
   start.bat
   ```

- **Mac/Linux:** Make the script executable and run:
  ```bash
   chmod +x start.sh
   ./start.sh
   ```

#### Option B: Manual Start (Two Terminals)

**Terminal 1 - Backend:**
```bash
# Make sure virtual environment is activated
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

### Step 5: Access the Application

1. Open your web browser
2. Navigate to: `http://localhost:3000`
3. You should see the Market Maker UI

### Step 6: Create Your Wallet

1. Click **"Create New Wallet"** in the UI
2. Your wallet will be saved to `wallet.json` (keep this file secure!)
3. Copy your public key

### Step 7: Get Test SOL (Devnet)

1. Visit the Solana Devnet Faucet: https://faucet.solana.com
2. Paste your public key
3. Request SOL (you can request multiple times)
4. Wait a few seconds for the transaction to confirm

### Step 8: Start Market Making

1. Check your balance in the Account Panel
2. Configure your settings in the Config Panel:
   - **Spread Percentage:** The profit margin (e.g., 0.5% = 0.5)
   - **Order Size:** Amount of SOL per order (e.g., 0.1 SOL)
   - **Minimum Balance:** Stop trading if balance drops below this
3. Click **"Start Market Maker"** in the Control Panel
4. Monitor your stats in real-time!

## Configuration

### Environment Variables (.env file)

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SOLANA_NETWORK` | Network to use | `devnet` | `devnet` or `mainnet-beta` |
| `RPC_URL` | Solana RPC endpoint | `https://api.devnet.solana.com` | Custom RPC URL |
| `WALLET_PATH` | Path to wallet file | `./wallet.json` | `./wallets/my_wallet.json` |
| `SPREAD_PERCENTAGE` | Default spread % | `0.5` | `1.0` |
| `ORDER_SIZE` | Default order size (SOL) | `0.1` | `0.5` |
| `MIN_BALANCE` | Minimum balance (SOL) | `1.0` | `2.0` |

### Switching Networks

**For Devnet (Testing):**
```
SOLANA_NETWORK=devnet
RPC_URL=https://api.devnet.solana.com
```

**For Mainnet (Production):**
```
SOLANA_NETWORK=mainnet-beta
RPC_URL=https://api.mainnet-beta.solana.com
```

⚠️ **Warning:** Always test thoroughly on devnet before using mainnet!

## Finding Trading Pairs & Testing on Mainnet

### Finding Trading Pairs

**Problem**: Devnet has limited liquidity and few real trading pairs, making it hard to test realistic conditions.

**Solution**: Use the included helper script to find available tokens:

```bash
# List tokens with liquidity on mainnet
python find-trading-pairs.py list mainnet

# Search for a specific token
python find-trading-pairs.py search USDC

# See well-known tokens
python find-trading-pairs.py well-known mainnet
```

**Alternative Methods**:
- **Jupiter Token List**: https://token.jup.ag/all (mainnet) or https://token.jup.ag/devnet
- **Jupiter Swap Interface**: https://jup.ag/ (browse tokens and copy mint addresses)
- **Solana Explorer**: https://explorer.solana.com/ (search for tokens)

### Testing on Mainnet

**⚠️ CRITICAL**: Mainnet uses **REAL SOL** - every transaction costs real money!

Before testing on mainnet, read the comprehensive guide:
- **[MAINNET_TESTING_GUIDE.md](MAINNET_TESTING_GUIDE.md)** - Complete guide covering:
  - All risks and potential problems
  - How to find trading pairs on both devnet and mainnet
  - Recommended testing strategy (start small!)
  - Emergency procedures
  - Pre-mainnet checklist

**Quick Start for Mainnet Testing**:
1. Read `MAINNET_TESTING_GUIDE.md` first
2. Use `find-trading-pairs.py` to find a high-liquidity token
3. Start with **minimal amounts** (0.01 SOL per trade)
4. Lower risk limits in your `.env`:
   ```
   BASE_TRADE_SIZE_SOL=0.01
   MAX_POSITION_SIZE_SOL=0.5
   MAX_EXPOSURE_PER_TOKEN=1.0
   TOTAL_MAX_EXPOSURE=2.0
   ```
5. Monitor closely and scale up gradually

## Project Structure

```
marketmaker/
├── backend/              # Python backend
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── config.py        # Configuration management
│   ├── solana_client.py # Solana blockchain integration
│   └── market_maker.py  # Market making logic
├── src/                 # React frontend
│   ├── components/      # UI components
│   ├── context/         # React context
│   └── App.tsx          # Main app component
├── requirements.txt     # Python dependencies
├── package.json         # Node.js dependencies
├── .env                 # Environment variables (create this)
└── README.md           # This file
```

## Using on Other Computers

To use this on another computer:

1. **Copy the entire project folder** to the new computer
2. **Follow the setup steps** (Steps 2-3) on the new computer
3. **Copy your `.env` file** (or recreate it with your settings)
4. **Copy your `wallet.json` file** if you want to use the same wallet
5. **Run the application** using the same steps

**Note:** The wallet file (`wallet.json`) contains your private key. Keep it secure and never share it!

## Security Best Practices

- 🔒 **Never commit** `wallet.json` or `.env` to version control
- 🔒 **Backup your wallet** file in a secure location
- 🔒 **Use devnet** for all testing
- 🔒 **Start with small amounts** when moving to mainnet
- 🔒 **Use a dedicated wallet** for market making (not your main wallet)
- 🔒 **Keep your private keys offline** when possible

## Troubleshooting

### Backend won't start
- Make sure Python virtual environment is activated
- Check that port 8000 is not in use
- Verify all dependencies are installed: `pip install -r requirements.txt`

### Frontend won't start
- Make sure Node.js is installed: `node --version`
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Check that port 3000 is not in use

### Wallet not loading
- Check that `wallet.json` exists in the project root
- Verify the file format is correct (should be a JSON array)
- Try creating a new wallet through the UI

### Can't connect to Solana
- Check your internet connection
- Verify the RPC URL in `.env` is correct
- Try using a different RPC endpoint

### Balance not updating
- Wait a few seconds (blockchain updates take time)
- Refresh the page
- Check the browser console for errors

## Next Steps

This is a basic market maker implementation. To enhance it:

1. **Add DEX Integration:** Connect to Raydium, Orca, or other DEXs
2. **Advanced Strategies:** Implement more sophisticated trading strategies
3. **Risk Management:** Add stop-loss, position limits, etc.
4. **Multiple Tokens:** Support trading multiple token pairs
5. **Historical Data:** Track and analyze past performance

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the code comments
- Test on devnet first

## License

This project is for educational purposes. Use at your own risk.

---

**⚠️ Disclaimer:** Trading cryptocurrencies involves risk. This software is provided as-is. Always test on devnet first and never invest more than you can afford to lose.
