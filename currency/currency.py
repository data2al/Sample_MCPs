  # 1. imports and constants

import os
from typing import Any
import httpx
from mcp.server.mcpserver import MCPServer

EXCHANGE_API_BASE = "https://open.er-api.com/v6/latest"
USER_AGENT = "currency-app/1.0"

# 2.Initialize FastMCP server
mcp = MCPServer("currency", version="1.0.0")

# 3. helper functions
async def make_exchange_request(base: str) -> dict[str, Any] | None:
    """Make a request to the exchange rate API with proper error handling."""
    url = f"{EXCHANGE_API_BASE}/{base.upper()}"
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            if data.get("result") != "success":
                return None
            return data
        except Exception:
            return None


# 4. @mcp.tool / @mcp.resource / @mcp.prompt
@mcp.tool()
async def get_exchange_rate(base: str, target: str) -> str:
    """Get the current exchange rate between two currencies.

    Args:
        base: Three-letter currency code to convert from (e.g. USD)
        target: Three-letter currency code to convert to (e.g. EUR)
    """
    data = await make_exchange_request(base)

    if not data:
        return f"Unable to fetch exchange rates for {base.upper()}."

    rates = data.get("rates", {})
    rate = rates.get(target.upper())
    if rate is None:
        return f"No rate found for {target.upper()} relative to {base.upper()}."

    return f"1 {base.upper()} = {rate} {target.upper()} (as of {data.get('time_last_update_utc', 'unknown time')})"


@mcp.tool()
async def convert(amount: float, base: str, target: str) -> str:
    """Convert an amount from one currency to another.

    Args:
        amount: Amount of money in the base currency
        base: Three-letter currency code to convert from (e.g. USD)
        target: Three-letter currency code to convert to (e.g. EUR)
    """
    data = await make_exchange_request(base)

    if not data:
        return f"Unable to fetch exchange rates for {base.upper()}."

    rates = data.get("rates", {})
    rate = rates.get(target.upper())
    if rate is None:
        return f"No rate found for {target.upper()} relative to {base.upper()}."

    converted = amount * rate
    return f"{amount} {base.upper()} = {converted:.2f} {target.upper()}"


# 5. Resources (URI-addressable read-only data):
@mcp.resource("currency://rates/{base}")
async def rates_resource(base: str) -> str:
    """All current exchange rates for a base currency."""
    data = await make_exchange_request(base)
    if not data:
        return f"Unable to fetch exchange rates for {base.upper()}."
    rates = data.get("rates", {})
    return "\n".join(f"{code}: {rate}" for code, rate in sorted(rates.items()))


# 6. Prompts (templated messages the host can surface as slash commands):
@mcp.prompt()
def conversion_briefing(base: str, target: str) -> str:
    """Generate a currency conversion briefing prompt."""
    return (
        f"Look up the current exchange rate from {base} to {target} and "
        f"explain what it means for someone converting money between them."
    )


# 7. Start the server with a transport
def main():
    port = os.environ.get("PORT")
    if port:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(port))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
