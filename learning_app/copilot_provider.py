"""GitHub Copilot SDK bridge for isolated, per-account tutor requests."""
import asyncio
import os
import tempfile


def _client_options(token, base_directory):
    runtime_env = {key: value for key, value in os.environ.items() if key.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA",
        "LOCALAPPDATA", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    }}
    runtime_env["COPILOT_TELEMETRY_DISABLED"] = "true"
    return {
        "github_token": token,
        "use_logged_in_user": False,
        "mode": "empty",
        "base_directory": base_directory,
        "env": runtime_env,
    }


async def _models(token):
    from copilot import CopilotClient

    with tempfile.TemporaryDirectory(prefix="postgres-lab-copilot-") as home:
        async with CopilotClient(**_client_options(token, home)) as client:
            return await client.list_models()


def list_models(token):
    return asyncio.run(_models(token))


async def _answer(token, model, instructions, messages):
    from copilot import CopilotClient

    transcript = "\n\n".join(f"{item['role'].title()}: {item['content']}" for item in messages)
    prompt = f"Conversation:\n{transcript}"
    with tempfile.TemporaryDirectory(prefix="postgres-lab-copilot-") as home:
        async with CopilotClient(**_client_options(token, home)) as client:
            async with await client.create_session(
                model=model,
                available_tools=[],
                enable_session_telemetry=False,
                system_message={"mode": "append", "content": instructions},
            ) as session:
                response = await session.send_and_wait(prompt)
                return response.data.content


def generate(token, model, instructions, messages):
    return asyncio.run(_answer(token, model, instructions, messages))
