import nox

nox.options.default_venv_backend = "uv"
UV_SYNC_COMMAND = ("uv", "sync", "--locked", "--no-dev")


@nox.session
def mypy(session: nox.Session) -> None:
    """Run mypy type checking.

    Args:
        session: Nox session.
    """
    session.run_install(
        *UV_SYNC_COMMAND,
        "--group=typing",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("mypy", *session.posargs)
