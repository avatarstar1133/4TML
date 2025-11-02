from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner

from agent import requirement_engineer_agent
from utils import call_agent_async
from dotenv import load_dotenv
import asyncio

load_dotenv()

db_url = "sqlite:///./my_agent_data.db"
session_service = DatabaseSessionService(db_url=db_url)

async def main_async():
    # Setup constants
    APP_NAME = "Requirement Engineering Agent"
    USER_ID = "sensei"

    # ===== PART 3: Session Creation =====
    # Create a new session with initial state
    existing_sessions = await session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID
    )

    # If there's an existing session, use it, otherwise create a new one
    if existing_sessions and len(existing_sessions.sessions) > 0:
        # Use the most recent session
        SESSION_ID = existing_sessions.sessions[0].id
        print(f"Continuing existing session: {SESSION_ID}")
    else:
        # Create a new session with initial state
        new_session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID
        )
        SESSION_ID = new_session.id
        print(f"Created new session: {SESSION_ID}")

    new_session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    SESSION_ID = new_session.id
    print(f"Created new session: {SESSION_ID}")

    # ===== PART 4: Agent Runner Setup =====
    # Create a runner with the main customer service agent
    runner = Runner(
        agent=requirement_engineer_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    with open('prompt.txt','r') as prompt:
        prompt_text = prompt.read()

    await call_agent_async(runner, USER_ID, SESSION_ID, prompt_text)

    print("\nI am your requirements engineering agent!")
    print("Type 'exit' or 'quit' to end the conversation.\n")

    while True:
        # Get user input
        user_input = input("You: ")

        # Check if user wants to exit
        if user_input.lower() in ["exit", "quit"]:
            print("Ending conversation. Goodbye!")
            break

        # Process the user query through the agent
        await call_agent_async(runner, USER_ID, SESSION_ID, user_input)


def main():
    """Entry point for the application."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()