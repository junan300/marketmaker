"""
Exchange Integration Layer — Jupiter Aggregator Adapter

Jupiter V6 API: https://station.jup.ag/docs/apis/swap-api
- Best-price quote fetching across all Solana DEXs
- Transaction building with slippage protection
- Rate limiting with token bucket algorithm
- Dynamic compute budget and priority fees
"""

import time
import asyncio
import logging
import httpx
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("dex.jupiter")

# Jupiter API endpoints (migrated from deprecated v6 to current lite-api)
JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"
JUPITER_SWAP_URL = "https://lite-api.jup.ag/swap/v1/swap"
JUPITER_PRICE_URL = "https://lite-api.jup.ag/price/v2"

# SOL mint address (native)
SOL_MINT = "So11111111111111111111111111111111111111112"


@dataclass
class SwapQuote:
    """Quote from Jupiter for a swap."""
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact_pct: float
    route_plan: list
    raw_quote: dict


@dataclass
class SwapResult:
    """Result of an executed swap."""
    tx_signature: str
    input_amount: int
    output_amount: int
    fill_price: float
    price_impact: float
    fee_sol: float
    success: bool
    error: str = ""


class RateLimiter:
    """Token bucket rate limiter for Jupiter API."""

    def __init__(self, max_per_second: float = 8, burst: int = 3):
        self.max_per_second = max_per_second
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.time()

    async def acquire(self):
        """Wait until a request slot is available."""
        while True:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.burst,
                self._tokens + elapsed * self.max_per_second,
            )
            self._last_refill = now

            if self._tokens >= 1:
                self._tokens -= 1
                return
            else:
                wait_time = (1 - self._tokens) / self.max_per_second
                await asyncio.sleep(wait_time)


class JupiterAdapter:
    """
    Jupiter V6 swap aggregator integration.
    Best-price routing across all Solana DEXs.
    """

    def __init__(
        self,
        default_slippage_bps: int = 100,  # 1% default slippage
        priority_fee_lamports: int = 50000,  # 0.00005 SOL priority fee
    ):
        self.default_slippage_bps = default_slippage_bps
        self.priority_fee_lamports = priority_fee_lamports
        self._rate_limiter = RateLimiter()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Price Queries ───────────────────────────────────────────────

    async def get_price(self, token_mint: str) -> Optional[float]:
        """Get current token price in USD from Jupiter.

        Tries the price API first, falls back to deriving price from a
        small quote (the v2 price API may require authentication).
        """
        # Try the price API first
        await self._rate_limiter.acquire()
        client = await self._get_client()

        try:
            response = await client.get(
                JUPITER_PRICE_URL,
                params={"ids": token_mint},
            )
            if response.status_code == 200:
                data = response.json()
                if "data" in data and token_mint in data["data"]:
                    return data["data"][token_mint]["price"]
        except Exception as e:
            logger.debug(f"Price API unavailable for {token_mint[:8]}...: {e}")

        # Fallback: derive price from a small quote (1 SOL -> token)
        try:
            quote = await self.get_quote(
                input_mint=SOL_MINT,
                output_mint=token_mint,
                amount=1_000_000_000,  # 1 SOL in lamports
            )
            if quote and quote.raw_quote.get("swapUsdValue"):
                # swapUsdValue is the USD value of the input (1 SOL)
                sol_usd = float(quote.raw_quote["swapUsdValue"])
                # Price per token = SOL_USD_price / tokens_per_SOL
                tokens_per_sol = quote.output_amount / (10 ** 6)  # assuming 6 decimals
                if tokens_per_sol > 0:
                    price_usd = sol_usd / tokens_per_sol
                    return price_usd
        except Exception as e:
            logger.error(f"Failed to derive price for {token_mint[:8]}...: {e}")

        return None

    async def get_price_in_sol(self, token_mint: str, amount_lamports: int = 1_000_000_000) -> Optional[float]:
        """Get how many tokens you get per SOL using a quote."""
        quote = await self.get_quote(
            input_mint=SOL_MINT,
            output_mint=token_mint,
            amount=amount_lamports,
        )
        if quote:
            return quote.output_amount
        return None

    # ── Quoting ─────────────────────────────────────────────────────

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = None,
    ) -> Optional[SwapQuote]:
        """Get a swap quote from Jupiter."""
        await self._rate_limiter.acquire()
        client = await self._get_client()

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps or self.default_slippage_bps,
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false",
        }

        try:
            response = await client.get(JUPITER_QUOTE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.error(f"Jupiter quote error: {data['error']}")
                return None

            return SwapQuote(
                input_mint=data["inputMint"],
                output_mint=data["outputMint"],
                input_amount=int(data["inAmount"]),
                output_amount=int(data["outAmount"]),
                price_impact_pct=float(data.get("priceImpactPct", 0)),
                route_plan=data.get("routePlan", []),
                raw_quote=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Jupiter quote HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Jupiter quote failed: {e}")
            return None

    # ── Swap Execution ──────────────────────────────────────────────

    async def build_swap_transaction(
        self,
        quote: SwapQuote,
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
    ) -> Optional[bytes]:
        """Build a swap transaction from a quote. Returns serialized tx bytes."""
        await self._rate_limiter.acquire()
        client = await self._get_client()

        payload = {
            "quoteResponse": quote.raw_quote,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": wrap_unwrap_sol,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": self.priority_fee_lamports,
        }

        try:
            response = await client.post(JUPITER_SWAP_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            if "swapTransaction" in data:
                import base64
                return base64.b64decode(data["swapTransaction"])
            else:
                logger.error(f"No swap transaction in response: {data}")
                return None

        except Exception as e:
            logger.error(f"Failed to build swap transaction: {e}")
            return None

    async def execute_swap(
        self,
        wallet_address: str,
        token_mint: str,
        side: str,
        amount_sol: float,
        max_slippage: float = 2.0,
        sign_and_send: callable = None,
    ) -> dict:
        """
        Full swap execution flow:
        1. Get quote  2. Check price impact  3. Build transaction
        4. Sign and send (via callback)  5. Return result
        """
        amount_lamports = int(amount_sol * 1_000_000_000)
        slippage_bps = int(max_slippage * 100)

        if side == "buy":
            input_mint = SOL_MINT
            output_mint = token_mint
        else:
            input_mint = token_mint
            output_mint = SOL_MINT

        # 1. Get quote
        quote = await self.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount_lamports,
            slippage_bps=slippage_bps,
        )

        if not quote:
            raise Exception("Failed to get swap quote from Jupiter")

        # 2. Check price impact
        if quote.price_impact_pct > max_slippage:
            raise Exception(
                f"Price impact too high: {quote.price_impact_pct:.2f}% "
                f"(max: {max_slippage}%)"
            )

        logger.info(
            f"Quote: {side} {amount_sol} SOL → "
            f"output={quote.output_amount} "
            f"impact={quote.price_impact_pct:.3f}% "
            f"routes={len(quote.route_plan)}"
        )

        # 3. Build transaction
        tx_bytes = await self.build_swap_transaction(
            quote=quote,
            user_public_key=wallet_address,
        )

        if not tx_bytes:
            raise Exception("Failed to build swap transaction")

        # 4. Sign and send
        if sign_and_send is None:
            raise Exception("No sign_and_send callback provided")

        tx_signature = await sign_and_send(tx_bytes)

        if not tx_signature:
            raise Exception("Transaction signing/sending failed")

        # 5. Calculate fill price
        if side == "buy":
            fill_price = amount_lamports / quote.output_amount if quote.output_amount > 0 else 0
        else:
            fill_price = quote.output_amount / amount_lamports if amount_lamports > 0 else 0

        return {
            "tx_signature": tx_signature,
            "filled_amount": amount_sol,
            "fill_price": fill_price,
            "output_amount": quote.output_amount,
            "price_impact": quote.price_impact_pct,
            "fee": self.priority_fee_lamports / 1_000_000_000,
        }

    def estimate_output(self, quote: SwapQuote) -> dict:
        """Human-readable output estimate."""
        return {
            "input": f"{quote.input_amount / 1e9:.6f} SOL" if quote.input_mint == SOL_MINT else f"{quote.input_amount} tokens",
            "output": f"{quote.output_amount / 1e9:.6f} SOL" if quote.output_mint == SOL_MINT else f"{quote.output_amount} tokens",
            "price_impact": f"{quote.price_impact_pct:.3f}%",
            "routes": len(quote.route_plan),
        }
