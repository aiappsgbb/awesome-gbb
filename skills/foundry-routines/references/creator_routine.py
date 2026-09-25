"""Canonical disabled creator-identity routine creation.

Source of truth for `../SKILL.md § Typed creator-identity management`.
Use only in the isolated management environment with an approved project client
and a fresh, exclusively owned name. No dispatch, login or consent side effects.
"""

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    InvokeAgentResponsesApiRoutineAction,
    Routine,
    RoutineAuthorization,
    ScheduleRoutineTrigger,
)
from azure.core.exceptions import ResourceNotFoundError


def create_creator_routine(
    project: AIProjectClient, routine_name: str, agent_name: str, input_text: str
) -> Routine:
    if not all(value and value.strip() for value in (routine_name, agent_name, input_text)):
        raise ValueError("Routine name, existing agent name and input must be nonempty")
    try:
        project.beta.routines.get(routine_name)
    except ResourceNotFoundError:
        pass
    else:
        raise ValueError("Creator authorization is create-only; choose a fresh routine name")

    project.beta.routines.create_or_update(
        routine_name=routine_name,
        enabled=False,
        authorization=RoutineAuthorization(identity="creator"),
        triggers={
            "weekday-morning": ScheduleRoutineTrigger(
                cron_expression="0 7 * * 1-5", time_zone="UTC"
            )
        },
        action=InvokeAgentResponsesApiRoutineAction(
            agent_name=agent_name, input=input_text
        ),
    )
    saved = project.beta.routines.get(routine_name)
    authorization = saved.as_dict().get("authorization")
    if (
        saved.name != routine_name
        or saved.enabled is not False
        or not isinstance(authorization, dict)
        or authorization.get("identity") != "creator"
    ):
        raise ValueError("Saved routine does not match disabled creator authorization; inspect before retrying")
    return saved
