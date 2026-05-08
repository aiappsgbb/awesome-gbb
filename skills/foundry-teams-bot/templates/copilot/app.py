"""aiohttp web server for the Teams bot."""

import logging
import os

from aiohttp import web
from microsoft_agents.activity import load_configuration_from_env
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.aiohttp import CloudAdapter, start_agent_process

from bot import AgentBot

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "80"))

# Parse CONNECTIONS__* env vars into SDK config
agents_sdk_config = load_configuration_from_env(os.environ)


def create_app() -> web.Application:
    """Create the aiohttp application with bot routes."""
    agent_configuration = MsalConnectionManager(**agents_sdk_config)
    adapter = CloudAdapter(connection_manager=agent_configuration)
    bot = AgentBot(adapter=adapter)
    app = start_agent_process(bot, adapter, agent_configuration)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
