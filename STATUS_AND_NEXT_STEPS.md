# Current Status & What's Missing for Mainnet Testing

## ✅ What's Already Done

1. **✅ .env Configured for Mainnet-Beta**
   - Network: `mainnet-beta`
   - RPC URL: `https://api.mainnet-beta.solana.com`
   - Passphrase: `Jjplopeza106..` (set)
   - Conservative trading settings (0.01 SOL per trade)

2. **✅ Wallet Keystore Exists**
   - Encrypted keystore at `data/wallets/keystore.enc`
   - Old wallet is stored (needs to be replaced/updated)

3. **✅ Jupiter Integration Ready**
   - Jupiter API already integrated
   - Can trade any pair available on Solana mainnet

4. **✅ Risk Management Configured**
   - Risk manager with circuit breakers
   - Conservative limits set in .env

## ❌ What's Missing to Test on Mainnet

### 1. **Server Needs Restart** ⚠️
   - Server is still running with OLD devnet configuration
   - **Action**: Restart the server to load new .env settings

### 2. **New Wallet Needs to be Imported** ⚠️
   - You mentioned you have a new wallet
   - Old wallet is still in the keystore
   - **Action**: Import your new wallet (private key)

### 3. **Wallet Needs Funding** ⚠️
   - Wallet needs real SOL on mainnet-beta
   - **Action**: Send SOL to your wallet address
   - Recommended: Start with 5-10 SOL for testing

### 4. **Token Selection** ⚠️
   - `TOKEN_MINT` is not set in .env
   - **Action**: Choose a token to market make
   - Use `find-trading-pairs.py` to find tokens

### 5. **Risk Limits Update** (Optional but Recommended)
   - Risk manager has hardcoded defaults (10 SOL per wallet)
   - Your .env has conservative limits (0.5 SOL)
   - **Action**: Update risk limits via API after server starts

---

## 🚀 Step-by-Step: Get Ready for Mainnet Testing

### Step 1: Restart the Server

**Stop current server:**
```powershell
# Find and kill Python processes
Get-Process python | Stop-Process -Force
```

**Or use the restart script:**
```powershell
.\restart-server.ps1
```

**Start backend:**
```bash
# Terminal 1
python -m uvicorn backend.main:app --reload --port 8000
```

**Start frontend:**
```bash
# Terminal 2
npm run dev
```

**Verify it's using mainnet:**
- Open: http://localhost:3000
- Check the Account Panel - should show "mainnet-beta"

---

### Step 2: Import Your New Wallet

**Option A: Via UI (Easiest)**
1. Open http://localhost:3000
2. Click "Import Existing Wallet"
3. Paste your private key (supports Base58, Hex, or Array format)
4. Click "Import Wallet"
5. Wallet will be encrypted and stored

**Option B: Via Script**
```bash
python import-wallet.py <your_private_key>
```

**Option C: Via API**
```bash
curl -X POST http://localhost:8000/api/wallet/import \
  -H "Content-Type: application/json" \
  -d '{"private_key": "YOUR_PRIVATE_KEY_HERE"}'
```

**Supported private key formats:**
- Base58: `5KQwr...`
- Hex: `0x1234...` or `1234...`
- Array: `[1,2,3,...]`

---

### Step 3: Fund Your Wallet

1. **Get your wallet address** from the UI (Account Panel)
2. **Send SOL** to that address on mainnet-beta
   - Use Phantom, Solflare, or any Solana wallet
   - Send from your main wallet to the trading wallet
   - **Recommended**: Start with 5-10 SOL

3. **Verify balance** in the UI

---

### Step 4: Choose a Token

**Find tokens with liquidity:**
```bash
# List available tokens
python find-trading-pairs.py list mainnet

# Search for specific token
python find-trading-pairs.py search USDC

# See well-known tokens
python find-trading-pairs.py well-known mainnet
```

**Recommended for initial testing:**
- **USDC** (stablecoin - low volatility): `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- **USDT** (stablecoin - low volatility): `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`

**Set token when starting:**
- Via UI: Enter token mint when starting market maker
- Via API: Include `token_mint` in start request

---

### Step 5: Update Risk Limits (Recommended)

After server starts, update risk limits to match your conservative .env settings:

**Via API:**
```bash
curl -X POST http://localhost:8000/api/v2/risk/rules \
  -H "Content-Type: application/json" \
  -d '{
    "max_position_size_per_wallet": 0.5,
    "max_exposure_per_token": 1.0,
    "total_max_exposure": 2.0,
    "max_daily_volume": 5.0
  }'
```

**Via UI:**
- Go to Risk Settings panel
- Update the limits manually

---

### Step 6: Start Trading!

1. **Set token mint** (if not in .env, set it when starting)
2. **Click "Start Market Maker"** in the UI
3. **Monitor closely** for the first few trades
4. **Check logs**: `data/market_maker.log`

---

## 📋 Quick Checklist

Before starting mainnet testing, verify:

- [ ] Server restarted (shows mainnet-beta in UI)
- [ ] New wallet imported (visible in Account Panel)
- [ ] Wallet funded with SOL (balance > 2 SOL)
- [ ] Token selected (USDC/USDT recommended for first test)
- [ ] Risk limits updated (optional but recommended)
- [ ] Conservative settings verified (0.01 SOL per trade)

---

## 🔍 Verify Everything is Ready

**Check server is using mainnet:**
```bash
curl http://localhost:8000/api/v2/status
```
Should show `"network": "mainnet-beta"`

**Check wallets:**
```bash
curl http://localhost:8000/api/v2/wallet/pool
```
Should show your new wallet

**Check wallet balance:**
- Use the UI Account Panel
- Or check on Solana Explorer: https://explorer.solana.com/

---

## ⚠️ Important Reminders

1. **Real Money**: Mainnet uses real SOL - every transaction costs money
2. **Start Small**: 0.01 SOL per trade is very conservative - perfect for testing
3. **Monitor Closely**: Watch the first few trades carefully
4. **Have Exit Plan**: Know how to stop quickly if needed
5. **Test Token First**: Use USDC/USDT (stablecoins) for lowest risk

---

## 🆘 If Something Goes Wrong

**Stop the market maker:**
```bash
curl -X POST http://localhost:8000/api/v2/stop
```

**Check logs:**
```bash
tail -f data/market_maker.log
```

**Check wallet on explorer:**
- https://explorer.solana.com/
- Search for your wallet address

---

## 📊 Current Configuration Summary

| Setting | Value | Status |
|---------|-------|--------|
| Network | mainnet-beta | ✅ Set |
| RPC URL | https://api.mainnet-beta.solana.com | ✅ Set |
| Passphrase | Jjplopeza106.. | ✅ Set |
| Base Trade Size | 0.01 SOL | ✅ Set |
| Min Balance | 2.0 SOL | ✅ Set |
| Stop Loss | 5.0% | ✅ Set |
| Wallet | ? | ❌ Need to import |
| Token | ? | ❌ Need to select |
| Server Running | ? | ❌ Need to restart |

---

**You're almost there!** Just need to:
1. Restart server
2. Import new wallet
3. Fund wallet
4. Choose token
5. Start trading!
