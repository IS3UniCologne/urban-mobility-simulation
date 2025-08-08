"""Noxfile for managing tests and other tasks."""

import nox

nox.options.default_venv_backend = "uv"
UV_SYNC_COMMAND = ("uv", "sync", "--locked", "--no-dev")


python_versions = nox.project.python_versions(nox.project.load_toml())


@nox.session(name="mypy", python=python_versions)
def mypy(session: nox.Session) -> None:
    """Run mypy type checking.

    Parameters
    ----------
    session : nox.Session
        Nox session.
    """
    session.run_install(
        *UV_SYNC_COMMAND,
        "--group=typing",
        "--python",
        session.python,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("mypy", *session.posargs)


@nox.session(name="pre-commit")
def pre_commit(session: nox.Session) -> None:
    """Run pre-commit linting and auto-fixes.

    Parameters
    ----------
    session: nox.Session
        Nox session.
    """
    args = session.posargs or ("run", "--all-files")
    session.run_install(
        *UV_SYNC_COMMAND,
        "--group=pre-commit",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("pre-commit", *args)


def _run_pytest(session: nox.Session) -> None:
    args = session.posargs or ("tests/",)

    session.run("pytest", "--durations=10", "-n=auto", "--dist=loadfile", *args)


@nox.session(name="pytest", python=python_versions, tags=("test", "pytest"))
def pytest_session(session: nox.Session) -> None:
    """Run pytest for unit and integration tests.

    Parameters
    ----------
    session: nox.Session
        Nox session.
    """
    session.run_install(
        *UV_SYNC_COMMAND,
        "--group=testing",
        "--python",
        session.python,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Force rebuild of Cython extensions
    session.run("uv", "pip", "install", "-e", ".", "--force-reinstall", "--no-deps")

    _run_pytest(session)
