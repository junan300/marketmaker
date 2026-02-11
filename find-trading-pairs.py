#!/usr/bin/env python3
"""
Helper script to find trading pairs available on Jupiter (devnet or mainnet).

This helps you find tokens with liquidity for testing your market maker.
"""

import httpx
import json
import sys
from typing import Optional

# Jupiter API endpoints
JUPITER_PRICE_URL_MAINNET = "https://price.jup.ag/v6/price"
JUPITER_PRICE_URL_DEVNET = "https://price.jup.ag/v6/price"
JUPITER_TOKEN_LIST_MAINNET = "https://token.jup.ag/all"
JUPITER_TOKEN_LIST_DEVNET = "https://token.jup.ag/devnet"

# Well-known token mints for testing
WELL_KNOWN_MAINNET = {
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "SOL": "So11111111111111111111111111111111111111112",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
}

WELL_KNOWN_DEVNET = {
    "USDC": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",  # May vary
    "SOL": "So11111111111111111111111111111111111111112",
}


def get_token_list(network: str = "mainnet") -> Optional[list]:
    """Fetch token list from Jupiter."""
    url = JUPITER_TOKEN_LIST_MAINNET if network == "mainnet" else JUPITER_TOKEN_LIST_DEVNET
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"❌ Failed to fetch token list: {e}")
        return None


def get_prices(network: str = "mainnet", token_ids: list = None) -> Optional[dict]:
    """Get prices for tokens from Jupiter."""
    url = JUPITER_PRICE_URL_MAINNET  # Same URL for both
    
    params = {}
    if token_ids:
        # Jupiter price API accepts comma-separated IDs or "all"
        if len(token_ids) > 50:
            params["ids"] = "all"  # Get all if too many
        else:
            params["ids"] = ",".join(token_ids)
    else:
        params["ids"] = "all"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {})
    except Exception as e:
        print(f"❌ Failed to fetch prices: {e}")
        return None


def find_tokens_with_liquidity(network: str = "mainnet", min_price: float = 0.0) -> list:
    """Find tokens that have price data (indicating liquidity)."""
    print(f"🔍 Fetching tokens with liquidity on {network}...")
    
    prices = get_prices(network)
    if not prices:
        print("⚠️  Could not fetch prices. Trying well-known tokens...")
        well_known = WELL_KNOWN_MAINNET if network == "mainnet" else WELL_KNOWN_DEVNET
        prices = get_prices(network, list(well_known.values()))
    
    if not prices:
        return []
    
    tokens = []
    for mint, data in prices.items():
        price = data.get("price", 0.0)
        if price >= min_price:
            tokens.append({
                "mint": mint,
                "price": price,
                "name": data.get("name", "Unknown"),
                "symbol": data.get("symbol", "?"),
            })
    
    # Sort by price (highest first)
    tokens.sort(key=lambda x: x["price"], reverse=True)
    return tokens


def search_token_list(query: str, network: str = "mainnet") -> list:
    """Search token list by name or symbol."""
    tokens = get_token_list(network)
    if not tokens:
        return []
    
    query_lower = query.lower()
    results = []
    
    for token in tokens:
        name = token.get("name", "").lower()
        symbol = token.get("symbol", "").lower()
        address = token.get("address", "").lower()
        
        if query_lower in name or query_lower in symbol or query_lower in address:
            results.append(token)
    
    return results


def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python find-trading-pairs.py list [mainnet|devnet]")
        print("  python find-trading-pairs.py search <query> [mainnet|devnet]")
        print("  python find-trading-pairs.py well-known [mainnet|devnet]")
        print()
        print("Examples:")
        print("  python find-trading-pairs.py list mainnet")
        print("  python find-trading-pairs.py search USDC")
        print("  python find-trading-pairs.py well-known mainnet")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    network = sys.argv[2].lower() if len(sys.argv) > 2 else "mainnet"
    
    if network not in ["mainnet", "devnet"]:
        print(f"❌ Invalid network: {network}. Use 'mainnet' or 'devnet'")
        sys.exit(1)
    
    if command == "list":
        print(f"\n📊 Finding tokens with liquidity on {network}...\n")
        tokens = find_tokens_with_liquidity(network)
        
        if not tokens:
            print("❌ No tokens found. This might be a network issue.")
            print("💡 Try using well-known tokens instead:")
            well_known = WELL_KNOWN_MAINNET if network == "mainnet" else WELL_KNOWN_DEVNET
            for symbol, mint in well_known.items():
                print(f"   {symbol}: {mint}")
            sys.exit(1)
        
        print(f"✅ Found {len(tokens)} tokens with price data:\n")
        print(f"{'Symbol':<12} {'Name':<30} {'Price (USD)':<15} {'Mint Address'}")
        print("-" * 100)
        
        for token in tokens[:50]:  # Show top 50
            symbol = token["symbol"][:12]
            name = token["name"][:30] if token["name"] else "Unknown"
            price = f"${token['price']:.6f}"
            mint = token["mint"]
            print(f"{symbol:<12} {name:<30} {price:<15} {mint}")
        
        if len(tokens) > 50:
            print(f"\n... and {len(tokens) - 50} more tokens")
        
        print(f"\n💡 To use a token, set TOKEN_MINT in your .env file:")
        print(f"   TOKEN_MINT={tokens[0]['mint']}")
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ Please provide a search query")
            print("   Example: python find-trading-pairs.py search USDC")
            sys.exit(1)
        
        query = sys.argv[2]
        print(f"\n🔍 Searching for '{query}' on {network}...\n")
        
        results = search_token_list(query, network)
        
        if not results:
            print(f"❌ No tokens found matching '{query}'")
            sys.exit(1)
        
        print(f"✅ Found {len(results)} matching tokens:\n")
        print(f"{'Symbol':<12} {'Name':<30} {'Mint Address'}")
        print("-" * 80)
        
        for token in results[:20]:  # Show top 20
            symbol = token.get("symbol", "?")[:12]
            name = token.get("name", "Unknown")[:30]
            mint = token.get("address", "?")
            print(f"{symbol:<12} {name:<30} {mint}")
        
        if len(results) > 20:
            print(f"\n... and {len(results) - 20} more results")
        
        if results:
            print(f"\n💡 To use a token, set TOKEN_MINT in your .env file:")
            print(f"   TOKEN_MINT={results[0].get('address')}")
    
    elif command == "well-known":
        well_known = WELL_KNOWN_MAINNET if network == "mainnet" else WELL_KNOWN_DEVNET
        
        print(f"\n📋 Well-known tokens on {network}:\n")
        print(f"{'Symbol':<12} {'Mint Address'}")
        print("-" * 80)
        
        for symbol, mint in well_known.items():
            print(f"{symbol:<12} {mint}")
        
        print(f"\n💡 These are good starting points for testing.")
        print(f"   For mainnet, USDC and USDT are stablecoins (low volatility).")
        print(f"   For devnet, liquidity may be limited.")
    
    else:
        print(f"❌ Unknown command: {command}")
        print("   Use 'list', 'search', or 'well-known'")
        sys.exit(1)


if __name__ == "__main__":
    main()
