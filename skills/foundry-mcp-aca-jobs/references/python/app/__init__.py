"""Canonical task-control package for foundry-mcp-aca-jobs.

Source of truth for the prose example in ../../../SKILL.md § Control record and lifecycle.
"""

from .aca_jobs import AcaExecution, AcaJobsAdapter, AcaJobsClient  # noqa: F401
from .aca_tasks_extension import AcaTasksExtension  # noqa: F401
from .callbacks import AsyncTokenCredential, CallbackSender, callback_payload  # noqa: F401
from .control_store import ControlStore, CosmosControlStore, InMemoryControlStore  # noqa: F401
from .job_worker import JobWorker, build_arg_parser as build_worker_arg_parser, build_worker_from_env, demo_handler  # noqa: F401
from .mcp_server import Runtime, build_server, owner_scope_from_headers, runtime_from_env  # noqa: F401
from .models import (  # noqa: F401
    CallbackDeliveryState,
    CallbackEvent,
    CallbackPolicy,
    GetTaskResult,
    JobPolicy,
    LifecycleState,
    Policy,
    PublicError,
    StartRequest,
    TaskRecord,
    map_aca_state,
    to_mcp_task,
)
from .orchestrator import Orchestrator  # noqa: F401
from .telemetry import Telemetry, configure, telemetry  # noqa: F401

__all__ = [
    'AcaExecution',
    'AcaJobsAdapter',
    'AcaJobsClient',
    'AcaTasksExtension',
    'AsyncTokenCredential',
    'CallbackDeliveryState',
    'CallbackEvent',
    'CallbackPolicy',
    'CallbackSender',
    'ControlStore',
    'CosmosControlStore',
    'GetTaskResult',
    'InMemoryControlStore',
    'JobPolicy',
    'JobWorker',
    'LifecycleState',
    'Orchestrator',
    'Policy',
    'PublicError',
    'Runtime',
    'StartRequest',
    'TaskRecord',
    'Telemetry',
    'build_server',
    'build_worker_arg_parser',
    'build_worker_from_env',
    'callback_payload',
    'configure',
    'demo_handler',
    'map_aca_state',
    'owner_scope_from_headers',
    'runtime_from_env',
    'telemetry',
    'to_mcp_task',
]
