# Contributing

This document outlines setting up the development environment and basic guidelines for working
on this repository.

> Just want to run your own experiments without contributing? See
> [Using this project for your own research](README.md#using-this-project-for-your-own-research)
> in the README. Most of the rules below won't apply to you.

## Development setup

Prerequisites:

- Python 3.11–3.13
- [uv](https://github.com/astral-sh/uv) for dependency management

> [!IMPORTANT]
> If you followed the README installation, this is the extra step you're missing.
> Install the git hooks (linting/formatting + commit message checks), otherwise
> these checks only fail later in CI:

```bash
uv run pre-commit install
```

If you have not done so already:

```bash
# Create a virtual environment and install all dependencies (incl. dev tools)
uv sync

# Optional extras
uv sync --extra ml    # machine learning and optimization dependencies
uv sync --extra viz   # visualization dependencies
uv sync --all-extras  # all the things
```

The Cython extension is built automatically during `uv sync`.

## Finding something to work on

We use an issue-first workflow: before starting non-trivial work, open a GitHub issue
(or comment on an existing one) so we can discuss the approach and avoid duplicate or
wasted effort. Trivial fixes (typos, small doc corrections etc.) can go straight
to a pull request.

## Branching and pull requests

We follow [trunk-based development](https://trunkbaseddevelopment.com/) with `develop` as
our trunk:

- Branch off `develop` and keep feature branches short-lived.
- If a branch sticks around longer, keep it up to date by merging `develop` into it.
- Open a pull request against `develop`. External contributors: fork the repository and
  open the PR from your fork.
- Every active feature branch should have an open pull request to track progress.
- PRs are merged with merge commits (no squashing), so clean up your commit history
  before merging. Every commit lands on `develop` as-is (see below).
- A maintainer reviews and merges your PR once checks pass.

## Commit messages

Every commit must follow the [Conventional Commits](https://www.conventionalcommits.org/)
specification. This is enforced in CI on every PR commit and locally by the `commit-msg`
hook installed above.

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.

```
feat: add relocation scheduler for shared vehicles
fix: handle users falling of the edge of the map
docs: update CONTRIBUTING.md :)
```

These commit messages feed into our automated release notes, so make sure they clearly
document all relevant changes in your branch.

For breaking changes, append `!` after the type (or add a `BREAKING CHANGE:` footer) and
describe the migration:

```
feat!: require datasets to declare a bounding box

BREAKING CHANGE: existing datasets without bounding_box.geojson must be
regenerated with `umosim new-dataset`.
```
These will get a very special spot at the top of the release notes, so everyone can see.

## Quality gates

We use [nox](https://nox.thea.codes/) for task automation. Run the full suite before
opening or updating a PR, or our CI will be very upset:

```bash
# Run everything below
nox -r

# Or individual sessions
nox -rs pyrefly      # type checking
nox -rs pre-commit   # linting and formatting (ruff etc.)
nox -rs pytest_fast  # fast test suite (everything except end-to-end)
nox -rs pytest_e2e   # end-to-end scenario suite
```

All test data is generated locally, no external data is required to run the full
test suite.

CI runs the same nox sessions on self-hosted runners. For PRs from forks, CI runs only after a maintainer approves the workflow run, so your local nox -r run is the primary gate.

## Code standards

*Most* of these are enforced by ruff and pyrefly, so `nox -r` will catch violations:

- **Type hints** everywhere, using modern syntax (`list[int]`, `str | None`). Parts of the
  codebase are still being migrated: new modules must type-check under pyrefly, so don't sneakily add entries to the `project-excludes` list in `pyproject.toml`. If you touch an excluded module, consider typing it and removing it from the list.
- **Docstrings** in [numpy style](https://numpydoc.readthedocs.io/en/latest/format.html)
  on public modules, classes, and functions. House conventions the linter can't check (yet):
  - Types in plain English ("int or None"), not type hint syntax.
  - Constructor arguments documented in the class docstring's `Parameters` section,
    not on `__init__`.
  - Properties get a one-line summary only, no `Returns` section.
  - Generators document their values under `Yields`, not `Returns`.
- **Logging** via the `logging` module with `%s`-style placeholders, never f-strings in
  log calls, never `print`.
- **Exceptions**: raise specific exception types with informative messages; custom
  exceptions live in `simulation/helper/exceptions.py`.
- **Configuration**: no hardcoded values, settings belong in the configuration class and
  `config_template.toml`.
- **Functions**: Try to keep them small and single-purpose.
- **Dependencies**: prefer the standard library; add third-party packages judiciously. This should always be discussed first.

### Gradual `# noqa` cleanup

The codebase still contains `# noqa` comments from the transition to ruff. If you modify
a function or class containing `# noqa` statements, please take the opportunity to fix
the underlying issue. Ruff automatically flags `# noqa` comments that are no longer
necessary.
