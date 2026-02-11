# Mainnet Testing Guide & Finding Trading Pairs

## ⚠️ Critical Risks When Testing on Mainnet

### 1. **Real Money Loss**
- **Mainnet uses REAL SOL** - every transaction costs real money
- Failed transactions still consume transaction fees (~0.000005 SOL + priority fees)
- Slippage and price impact can be much higher than devnet
- **Recommendation**: Start with **minimal amounts** (0.01-0.1 SOL per trade)

### 2. **Transaction Fees & Priority Fees**
- **Base transaction fee**: ~0.000005 SOL per transaction
- **Priority fees**: Can be 0.00005-0.001 SOL during network congestion
- **Failed transactions still cost fees** - if a trade fails, you still pay
- **Recommendation**: Monitor your balance closely, set `MIN_BALANCE` higher (2-5 SOL)

### 3. **Network Congestion & Failed Transactions**
- Mainnet can be congested, causing:
  - Transaction timeouts
  - Higher priority fees needed
  - Failed swaps (you still pay fees)
- **Your risk manager has circuit breakers**, but failed transactions still cost money
- **Recommendation**: Use a **reliable RPC endpoint** (not the free public one)

### 4. **Slippage & Price Impact**
- Mainnet has **real liquidity** - but also real volatility
- Low-liquidity tokens can have **massive slippage** (5-20%+)
- Your `MAX_SLIPPAGE_PERCENT` (default 2%) may be too strict for some tokens
- **Recommendation**: 
  - Test with **high-liquidity tokens** first (USDC, USDT, popular tokens)
  - Adjust `MAX_SLIPPAGE_PERCENT` based on token liquidity
  - Monitor `price_impact_pct` in logs

### 5. **RPC Rate Limiting**
- Free public RPC endpoints (`https://api.mainnet-beta.solana.com`) have strict rate limits
- You may get **429 Too Many Requests** errors
- **Recommendation**: 
  - Use a **paid RPC provider** (Helius, QuickNode, Alchemy)
  - Or use Jupiter's rate limiter (already implemented, but may need tuning)

### 6. **Smart Contract Risks**
- Jupiter aggregator is generally safe, but:
  - Token contracts can have bugs
  - Rug pulls on low-cap tokens
  - **Recommendation**: Only trade **verified, well-known tokens**

### 7. **Wallet Security**
- Mainnet wallets contain **real value**
- If your `.env` or keystore is compromised, funds are at risk
- **Recommendation**: 
  - Use a **dedicated trading wallet** (not your main wallet)
  - Keep minimal funds in the trading wallet
  - Enable all security features

### 8. **Risk Manager Limits**
- Your risk manager has default limits that may be too high for initial testing:
  - `max_position_size_per_wallet: 10.0 SOL`
  - `max_exposure_per_token: 50.0 SOL`
  - `total_max_exposure: 100.0 SOL`
- **Recommendation**: **Lower these limits** for initial mainnet testing:
  ```python
  # In your .env or via API
  MAX_POSITION_SIZE_SOL=1.0
  MAX_EXPOSURE_PER_TOKEN=5.0
  TOTAL_MAX_EXPOSURE=10.0
  ```

### 9. **Stop Loss Execution**
- Stop losses execute **market orders** - they can fill at worse prices during volatility
- During flash crashes, stop loss may execute far below your threshold
- **Recommendation**: Test stop loss behavior on devnet first

### 10. **Jupiter API Issues**
- Jupiter API can be down or slow
- Quote failures will prevent trading
- **Recommendation**: Monitor Jupiter API status, have fallback plans

---

## 🔍 Finding Trading Pairs on Devnet

### Problem: Devnet has limited liquidity and few real trading pairs

### Solutions:

#### Option 1: Use Jupiter Token List (Recommended)
Jupiter maintains token lists for both devnet and mainnet:

**Devnet Token List:**
```
https://token.jup.ag/devnet
```

**Mainnet Token List:**
```
https://token.jup.ag/all
```

You can browse these to find tokens with liquidity.

#### Option 2: Use Jupiter Price API to Find Active Tokens
```bash
# Get all tokens with prices (devnet)
curl "https://price.jup.ag/v6/price?ids=all"
```

This will show you which tokens have active price feeds (indicating liquidity).

#### Option 3: Use Solana Explorer
- **Devnet Explorer**: https://explorer.solana.com/?cluster=devnet
- Search for token mints or look at recent token transfers

#### Option 4: Create Your Own Test Token (Devnet Only)
1. Use Solana CLI or a token creation tool
2. Create a token on devnet
3. Add liquidity to a DEX (Raydium, Orca) on devnet
4. Use that token mint address

#### Option 5: Use Well-Known Devnet Tokens
Some tokens that often have devnet liquidity:
- **USDC Devnet**: `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU` (may vary)
- **USDT Devnet**: Check Jupiter token list

**Note**: Devnet liquidity is often very low or non-existent. This is why testing on devnet is limited.

---

## 🔍 Finding Trading Pairs on Mainnet

### Option 1: Jupiter Token List (Best Option)
Visit: **https://token.jup.ag/all**

This shows:
- Token name and symbol
- Token mint address
- Market cap
- Liquidity indicators

**Popular high-liquidity tokens for testing:**
- **USDC**: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- **USDT**: `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`
- **BONK**: `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`
- **WIF**: `EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm`

### Option 2: Jupiter Swap Interface
1. Go to **https://jup.ag/**
2. Connect wallet (or just browse)
3. Search for tokens
4. Copy the token mint address from the URL or token info

### Option 3: CoinGecko / CoinMarketCap
1. Find a token you want to trade
2. Look for the Solana contract address
3. Use that as your `TOKEN_MINT`

### Option 4: Solana Explorer
- **Mainnet Explorer**: https://explorer.solana.com/
- Search for token names or mint addresses
- Check token holder count and recent activity

### Option 5: DEX Interfaces
- **Raydium**: https://raydium.io/
- **Orca**: https://www.orca.so/
- Browse tokens and copy mint addresses

---

## 🧪 Recommended Mainnet Testing Strategy

### Phase 1: Minimal Risk Testing (Week 1)
1. **Start with stablecoins** (USDC/USDT) - minimal volatility
2. **Use tiny trade sizes**: `BASE_TRADE_SIZE_SOL=0.01`
3. **Lower all risk limits**:
   ```
   MAX_POSITION_SIZE_SOL=0.5
   MAX_EXPOSURE_PER_TOKEN=1.0
   TOTAL_MAX_EXPOSURE=2.0
   MAX_DAILY_VOLUME=5.0
   ```
4. **Monitor closely** - watch every trade
5. **Set strict stop loss**: `STOP_LOSS_PERCENT=5.0`

### Phase 2: Small Scale (Week 2-3)
1. **Increase trade sizes gradually**: `BASE_TRADE_SIZE_SOL=0.05`
2. **Test with one volatile token** (but high liquidity)
3. **Gradually increase limits** as you gain confidence
4. **Monitor performance metrics**

### Phase 3: Production Scale (After 1+ month)
1. **Only after extensive testing**
2. **Gradually scale up** position sizes
3. **Monitor risk metrics daily**

---

## 🔧 Pre-Mainnet Checklist

Before testing on mainnet, verify:

- [ ] **Wallet has minimal funds** (start with 5-10 SOL max)
- [ ] **Risk limits are conservative** (see Phase 1 above)
- [ ] **Stop loss is enabled** and tested
- [ ] **RPC endpoint is reliable** (consider paid provider)
- [ ] **Token has high liquidity** (check Jupiter)
- [ ] **Slippage settings are appropriate** for token liquidity
- [ ] **Emergency shutdown procedure** is understood
- [ ] **Logs are being monitored**
- [ ] **Database backups** are configured
- [ ] **You understand how to stop** the market maker quickly

---

## 🚨 Emergency Procedures

### If Something Goes Wrong:

1. **Stop the market maker immediately**:
   ```bash
   # Via API
   curl -X POST http://localhost:8000/api/v2/stop
   
   # Or kill the process
   ```

2. **Check your positions**:
   - Review database for open positions
   - Check wallet balance on Solana Explorer

3. **Manual exit** (if needed):
   - Use Jupiter swap interface to manually close positions
   - Or use Solana CLI

4. **Review logs**:
   ```bash
   # Check backend logs
   tail -f data/market_maker.log
   ```

---

## 📊 Monitoring on Mainnet

### Key Metrics to Watch:

1. **Balance**: Monitor SOL balance - should not drop unexpectedly
2. **Failed Transactions**: Watch for consecutive failures (circuit breaker will trip)
3. **Slippage**: Check if actual slippage matches expected
4. **Position Count**: Ensure positions are being opened/closed correctly
5. **Profit/Loss**: Track cumulative P&L
6. **Risk Manager Status**: Check `/api/v2/risk/status` regularly

### Recommended Monitoring Tools:

- **Solana Explorer**: Monitor wallet transactions
- **Jupiter Dashboard**: Check swap history
- **Your Application Logs**: `data/market_maker.log`
- **Database**: Query trading history

---

## 💡 Devnet vs Mainnet Differences

| Aspect | Devnet | Mainnet |
|--------|--------|---------|
| **Cost** | Free (faucet SOL) | Real SOL (real money) |
| **Liquidity** | Very low/nonexistent | Real liquidity |
| **Volatility** | Artificial | Real market conditions |
| **Transaction Speed** | Fast (less congestion) | Variable (can be slow) |
| **Fees** | Free | Real fees |
| **Token Availability** | Limited | Full ecosystem |
| **Testing Value** | Code testing | Real-world validation |

**Conclusion**: Devnet is great for testing **code functionality**, but mainnet is needed for **real-world conditions**. However, start **very small** on mainnet!

---

## 🔗 Useful Links

- **Jupiter Token List (Mainnet)**: https://token.jup.ag/all
- **Jupiter Token List (Devnet)**: https://token.jup.ag/devnet
- **Jupiter Swap Interface**: https://jup.ag/
- **Solana Explorer (Mainnet)**: https://explorer.solana.com/
- **Solana Explorer (Devnet)**: https://explorer.solana.com/?cluster=devnet
- **Jupiter API Docs**: https://station.jup.ag/docs/apis/swap-api
- **Solana Faucet (Devnet)**: https://faucet.solana.com/

---

## ❓ Quick Reference: Setting Up for Mainnet

```env
# .env file for mainnet testing
SOLANA_NETWORK=mainnet-beta
RPC_URL=https://api.mainnet-beta.solana.com  # Or use paid RPC
TOKEN_MINT=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v  # USDC example

# Conservative risk settings
BASE_TRADE_SIZE_SOL=0.01
MAX_POSITION_SIZE_SOL=0.5
MAX_EXPOSURE_PER_TOKEN=1.0
TOTAL_MAX_EXPOSURE=2.0
MAX_DAILY_VOLUME=5.0
STOP_LOSS_PERCENT=5.0
MAX_SLIPPAGE_PERCENT=2.0
MIN_BALANCE=2.0

# Trading config
CYCLE_INTERVAL_S=30  # Slower cycles for mainnet
```

**Remember**: Start small, monitor closely, and scale up gradually!
