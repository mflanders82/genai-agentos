import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import multiprocessing
import typer

from uuid import uuid4
from src.exceptions import APIError
from src.utils import cli_error_renderer, load_jwt, validate_uuid
from src.log import prettify_json, render_success, render_error
from src.http import http_repo
from src.jinja.file_generator import generate_agent_file
from src.launch_all_agents import AgentDependencyManager

app = typer.Typer(
    help="GenAI CLI app",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=True,
)


@app.command(name="login")
@cli_error_renderer
def login(
    username: str = typer.Option(..., "--username", "-u", help="Your genai username"),
    password: str = typer.Option(
        ...,
        "--password",
        "-p",
        prompt="Please enter your genai password",
        hide_input=True,
        help="Your password (will be prompted securely if not provided).",
    ),
):
    return asyncio.run(http_repo.login_user(username=username, password=password))


@app.command(name="signup")
@cli_error_renderer
def register(
    username: str = typer.Option(..., "--username", "-u", help="Your genai username"),
    password: str = typer.Option(
        ...,
        prompt="Please enter your genai password",
        hide_input=True,
        help="Your password (will be prompted securely if not provided).",
    ),
):
    try:
        return asyncio.run(
            http_repo.register_user(username=username, password=password)
        )
    except APIError as e:
        render_error(str(e))
        return


@app.command(name="logout")
def logout():
    return http_repo.creds_manager.logout()


@app.command(name="list_agents")
@cli_error_renderer
def list_agents(limit: int = 100, offset: int = 0):
    try:
        user_jwt = load_jwt(http_repo=http_repo)
        result = asyncio.run(
            http_repo.list_agents(
                limit=limit,
                offset=offset,
                headers={"Authorization": f"Bearer {user_jwt}"},
            )
        )
        render_success(prettify_json(result.json()))
        return
    except APIError as e:
        render_error(str(e))
        return


@app.command(name="register_agent")
@cli_error_renderer
def register_agent(
    agent_id: str = typer.Option(
        str(uuid4()), "--id", help="Unique user id (uuid) for your agent"
    ),
    name: str = typer.Option(..., "-n", "--name", help="Name of your agent"),
    description: str = typer.Option(
        ...,
        "-d",
        "--description",
        help="Description of your agent. Make sure it is as self-explanatory as possible",
    ),
):
    agent_id = validate_uuid(value=agent_id, field_name="agent_id")
    if not agent_id:
        return

    user_jwt = load_jwt(http_repo=http_repo)

    # new event loop is needed as no event loop exists when cli command is being invoked
    # and two async methods need to be invoked from sync function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    register_result = loop.run_until_complete(
        http_repo.register_agent(
            agent_id=agent_id,
            name=name,
            description=description,
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
    )
    render_success(
        f"Registered agent '{register_result.json()['id']}' successfully. Generating agent body..."
    )

    agent = loop.run_until_complete(
        http_repo.lookup_agent(
            agent_id=agent_id, headers={"Authorization": f"Bearer {user_jwt}"}
        )
    )
    if not agent:
        loop.run_until_complete(
            http_repo.delete_agent(
                agent_id=register_result.json()["id"],
                headers={"Authorization": f"Bearer {user_jwt}"},
            )
        )
        return

    generate_agent_file(agent_body=agent)
    loop.close()
    return


@app.command(name="delete_agent")
@cli_error_renderer
def delete_agent(
    agent_id: str = typer.Option(
        ..., "--id", help="Unique user id (uuid) of your agent created earlier"
    ),
):
    agent_id = validate_uuid(value=agent_id, field_name="agent_id")
    if not agent_id:
        return
    user_jwt = load_jwt(http_repo=http_repo)
    is_deleted = asyncio.run(
        http_repo.delete_agent(
            agent_id=agent_id, headers={"Authorization": f"Bearer {user_jwt}"}
        )
    )
    if is_deleted:
        render_success(f"Agent {agent_id} was deleted successfully")
        return

    else:
        raise APIError(
            "HTTP request was successful, but unexpectedly failed to delete the agent."
        )


@app.command(name="generate_agent")
@cli_error_renderer
def generate_agent(
    agent_id: str = typer.Option(
        ..., "--id", help="Unique user id (uuid) of your agent created earlier"
    ),
):
    agent_id = validate_uuid(value=agent_id, field_name="agent_id")
    if not agent_id:
        return

    user_jwt = load_jwt(http_repo=http_repo)
    agent = asyncio.run(
        http_repo.lookup_agent(
            agent_id=agent_id, headers={"Authorization": f"Bearer {user_jwt}"}
        )
    )
    if not agent:
        return

    generate_agent_file(agent_body=agent)
    return


@app.command(name="run_agents")
@cli_error_renderer
def run_agents():
    manager = AgentDependencyManager()
    manager.run()
    return


if __name__ == "__main__":
    multiprocessing.freeze_support()
    multiprocessing.set_start_method("spawn", force=True)
    app()
