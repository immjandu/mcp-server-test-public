import asyncio
import logging
import os
import secrets
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth.providers.debug import DebugTokenVerifier

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


def validate_api_token(token: str) -> bool:
    """Validate Bearer token against MCP_API_TOKEN env var."""
    expected = os.getenv("MCP_API_TOKEN")
    if not expected:
        return False
    return secrets.compare_digest(token, expected)


auth = DebugTokenVerifier(validate=validate_api_token, client_id="weather-mcp-client")
mcp = FastMCP("weather MCP Server on Kakaocloud (authenticated)", auth=auth)


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get("event", "Unknown")}
Area: {props.get("areaDesc", "Unknown")}
Severity: {props.get("severity", "Unknown")}
Description: {props.get("description", "No description available")}
Instructions: {props.get("instruction", "No specific instructions provided")}
"""


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:
        forecast = f"""
{period["name"]}:
Temperature: {period["temperature"]}°{period["temperatureUnit"]}
Wind: {period["windSpeed"]} {period["windDirection"]}
Forecast: {period["detailedForecast"]}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


def main():
    try:
        if not os.getenv("MCP_API_TOKEN"):
            raise ValueError(
                "MCP_API_TOKEN environment variable must be set. "
                "Clients must send Authorization: Bearer <token>."
            )

        port = int(os.getenv("PORT", "8000"))
        logger.info(f"Starting authenticated MCP server on port {port}")

        asyncio.run(
            mcp.run_http_async(
                transport="streamable-http",
                host="0.0.0.0",
                port=port,
                allowed_hosts=["*.playmcp-endpoint.kakaocloud.io"]
            )
        )
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
