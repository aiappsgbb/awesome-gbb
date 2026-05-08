"""aiohttp web server for the Teams bot."""

import asyncio
import logging
import os

from aiohttp import web
from microsoft_agents.hosting.aiohttp import start_agent_process

from bot import setup

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "80"))


async def create_app() -> web.Application:
    """Create the aiohttp application with bot routes."""
    agent_app, connection_manager = await setup()
    app = start_agent_process(agent_app, agent_app._adapter, connection_manager)
    return app


if __name__ == "__main__":
    app = asyncio.run(create_app())
    web.run_app(app, host="0.0.0.0", port=PORT)
