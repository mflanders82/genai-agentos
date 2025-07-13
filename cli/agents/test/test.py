import asyncio
from typing import Annotated
from genai_session.session import GenAISession
from genai_session.utils.context import GenAIContext

AGENT_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YjQzMTYxZS1mMmRjLTQ1YjgtYTYxYi04YTIzMDQ2YjJlNjUiLCJleHAiOjI1MzQwMjMwMDc5OSwidXNlcl9pZCI6Ijg5ZTQ2YzcyLTc5ZTYtNGQyOS04YjFhLWFiNDFjNWZlYjUzNiJ9.HcSXn62Rbu4y9jKnkkcGOjOERqdsM0enzqJsVUPbdNY" # noqa: E501
session = GenAISession(jwt_token=AGENT_JWT)


@session.bind(
    name="test",
    description="testing agent"
)
async def test(
    agent_context: GenAIContext,
    test_arg: Annotated[
        str,
        "This is a test argument. Your agent can have as many parameters as you want. Feel free to rename or adjust it to your needs.",  # noqa: E501
    ],
):
    """testing agent"""
    return "Hello, World!"


async def main():
    print(f"Agent with token '{AGENT_JWT}' started")
    await session.process_events()

if __name__ == "__main__":
    asyncio.run(main())
