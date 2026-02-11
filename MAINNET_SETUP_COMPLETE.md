# Mainnet-Beta Setup Complete ✅

## Configuration Summary

Your `.env` file has been configured for **mainnet-beta** testing with conservative settings.

### ✅ What's Been Configured

1. **Network**: `mainnet-beta` (real Solana network)
2. **RPC URL**: `https://api.mainnet-beta.solana.com`
3. **Passphrase**: Updated to your new passphrase
4. **Conservative Trading Settings**:
   - Base trade size: **0.01 SOL** (very small for initial testing)
   - Cycle interval: **30 seconds** (slower cycles)
   - Min balance: **2.0 SOL** (safety buffer)
   - Stop loss: **5.0%** (tighter than default 10%)

### ⚠️ Important Notes

#### Risk Manager Default Limits
The risk manager has **hardcoded defaults** that are higher than your conservative .env settings:
- `max_position_size_per_wallet`: **10.0 SOL** (default)
- `max_exposure_per_token`: **50.0 SOL** (default)
- `total_max_exposure`: **100.0 SOL** (default)

**You can update these via API** after starting the server:
```bash
# Update risk limits to match your conservative .env settings
curl -X POST http://localhost:8000/api/v2/risk/rules \
  -H "Content-Type: application/json" \
  -d '{
    "max_position_size_per_wallet": 0.5,
    "max_exposure_per_token": 1.0,
    "total_max_exposure": 2.0,
    "max_daily_volume": 5.0
  }'
```

Or use the UI to update risk settings.

#### Token Selection
**TOKEN_MINT is not set** - you need to choose a token when starting the market maker.

**Find tokens with liquidity:**
```bash
# List available tokens
python find-trading-pairs.py list mainnet

# Search for a specific token
python find-trading-pairs.py search USDC

# See well-known tokens
python find-trading-pairs.py well-known mainnet
```

**Recommended for initial testing:**
- **USDC** (stablecoin - low volatility): `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- **USDT** (stablecoin - low volatility): `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`

## Next Steps

### 1. Start the Application
```bash
# Windows
start.bat

# Or manually:
# Terminal 1
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2
npm run dev
```

### 2. Access the UI
Open: http://localhost:3000

### 3. Create/Import Wallet
- If you don't have a wallet, create one in the UI
- If you have an existing wallet, import it
- **IMPORTANT**: Fund your wallet with **real SOL** on mainnet-beta
  - Start with **5-10 SOL** for initial testing
  - You can always add more later

### 4. Update Risk Limits (Recommended)
Before starting trading, update risk limits to match your conservative settings:
- Via UI: Go to Risk Settings panel
- Via API: Use the curl command above

### 5. Choose a Token
- Use `find-trading-pairs.py` to find tokens
- Or browse: https://token.jup.ag/all
- Start with **USDC or USDT** for lowest volatility

### 6. Start Trading
- Set `TOKEN_MINT` in the UI or via API
- Click "Start Market Maker"
- **Monitor closely** for the first few hours

## Current Configuration Values

| Setting | Value | Purpose |
|---------|-------|---------|
| `SOLANA_NETWORK` | `mainnet-beta` | Real network |
| `BASE_TRADE_SIZE_SOL` | `0.01` | Very small trades |
| `MIN_BALANCE` | `2.0` | Safety buffer |
| `CYCLE_INTERVAL_S` | `30.0` | Slower cycles |
| `STOP_LOSS_PERCENT` | `5.0` | Tighter stop loss |
| `MAX_SLIPPAGE_PERCENT` | `2.0` | Max slippage tolerance |
| `MAX_TRADE_SIZE_SOL` | `0.5` | Cap per trade |

## ⚠️ Safety Reminders

1. **Real Money**: Mainnet uses **real SOL** - every transaction costs money
2. **Start Small**: 0.01 SOL per trade is very conservative - good for testing
3. **Monitor Closely**: Watch the first few trades carefully
4. **Update Risk Limits**: Don't forget to lower risk manager defaults
5. **Have Exit Plan**: Know how to stop the market maker quickly if needed

## Useful Commands

```bash
# Find trading pairs
python find-trading-pairs.py list mainnet

# Check risk manager status
curl http://localhost:8000/api/v2/risk/status

# Stop market maker
curl -X POST http://localhost:8000/api/v2/stop

# Check market maker status
curl http://localhost:8000/api/v2/status
```

## Need Help?

- Read `MAINNET_TESTING_GUIDE.md` for comprehensive information
- Check logs: `data/market_maker.log`
- Monitor wallet on Solana Explorer: https://explorer.solana.com/

---

**You're all set!** 🚀

Remember: Start small, monitor closely, and scale up gradually as you gain confidence.
