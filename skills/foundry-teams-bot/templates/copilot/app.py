"""aiohttp web server for the Teams bot."""

import asyncio
import logging
import os

from aiohttp.web import Request, Response, Application, run_app
from microsoft_agents.hosting.core import AgentApplication
from microsoft_agents.hosting.aiohttp import (
    start_agent_process,
    jwt_authorization_middleware,
    CloudAdapter,
)

from bot import setup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("azure").setLevel(logging.WARNING)


async def init_app() -> Application:
    agent_app, auth_configuration = await setup()
    APP = Application(middlewares=[jwt_authorization_middleware])
    APP.router.add_post("/api/messages", entry_point)
    APP["agent_configuration"] = (
        auth_configuration.get_default_connection_configuration()
    )
    APP["agent_app"] = agent_app
    APP["adapter"] = agent_app.adapter
    return APP


async def entry_point(req: Request) -> Response:
    agent: AgentApplication = req.app["agent_app"]
    adapter: CloudAdapter = req.app["adapter"]
    response = await start_agent_process(req, agent, adapter)
    if response is None:
        return Response(status=500, text="Internal Server Error")
    return response


if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 80))
        host = os.environ.get("HOST", "0.0.0.0")
        app = asyncio.run(init_app())
        logger.info(f"Starting app on {host}:{port}")
        run_app(app, host=host, port=port)
    except Exception as error:
        logger.critical(f"Error starting app: {error}")
        raise error
