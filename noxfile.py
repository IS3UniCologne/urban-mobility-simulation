"""Noxfile for managing tests and other tasks."""

import shutil

import nox

nox.options.default_venv_backend = "uv"
UV_SYNC_COMMAND = ("uv", "sync", "--locked", "--no-dev")


python_versions = nox.project.python_versions(nox.project.load_toml())


@nox.session(name="pyrefly", python=python_versions)
def pyrefly(session: nox.Session) -> None:
    """Run pyrefly type checking.

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
    session.run("pyrefly", "check", *session.posargs)


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


@nox.session(name="docs")
def docs(session: nox.Session) -> None:
    """Build the HTML documentation into docs/_build/html, failing on any warning.

    Parameters
    ----------
    session : nox.Session
        Nox session.
    """
    session.run_install(
        *UV_SYNC_COMMAND,
        "--group=docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    # Leftover stubs, doctrees or cached inventories would make the build differ from CI
    for build_dir in ("docs/_autosummary", "docs/_build"):
        shutil.rmtree(build_dir, ignore_errors=True)
    session.run(
        "sphinx-build",
        "-W",
        "--keep-going",
        "-b",
        "html",
        "docs",
        "docs/_build/html",
        *session.posargs,
    )


def _install_testing(session: nox.Session) -> None:
    session.run_install(
        *UV_SYNC_COMMAND,
        "--group=testing",
        "--python",
        session.python,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    # Force rebuild of Cython extensions
    session.run("uv", "pip", "install", "-e", ".", "--force-reinstall", "--no-deps")


@nox.session(name="pytest_fast", python=python_versions, tags=("test", "pytest"))
def pytest_fast(session: nox.Session) -> None:
    """Run the fast pytest suite (everything except end-to-end tests).

    Parameters
    ----------
    session: nox.Session
        Nox session.
    """
    _install_testing(session)
    args = session.posargs or ("-m", "not end_to_end", "tests/")
    session.run("pytest", "--durations=10", "-n=auto", "--dist=loadfile", *args)


@nox.session(name="pytest_e2e", python=python_versions, tags=("test", "e2e"))
def pytest_e2e(session: nox.Session) -> None:
    """Run the full end-to-end scenario suite.

    Parameters
    ----------
    session: nox.Session
        Nox session.
    """
    _install_testing(session)
    session.run(
        "pytest",
        "--durations=10",
        "-n=auto",
        "--dist=loadfile",
        "-m",
        "end_to_end",
        "tests/end_to_end",
    )
