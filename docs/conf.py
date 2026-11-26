"""Sphinx configuration for the urban-mobility-simulation documentation."""

from __future__ import annotations

import json
import os
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.util.logging import getLogger

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

logger = getLogger(__name__)

project = "urban-mobility-simulation"
package_version = metadata.version(project)
_docs_url = "https://umosim.readthedocs.io"

# Read the Docs reports "stable" and each release as type "tag", develop as "branch"
_is_release_build = os.environ.get("READTHEDOCS_VERSION_TYPE") == "tag"
release = version = package_version if _is_release_build else "develop"
# Releases read the list the develop build writes, so an old release learns of newer ones
switcher_json_url = (
    f"{_docs_url}/latest/_static/switcher.json"
    if _is_release_build
    else "_static/switcher.json"
)

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxarg.ext",
    "sphinxcontrib.autodoc_pydantic",
]
# Only top-level pages and the generated API stubs are sources, so other subfolders stay out
include_patterns = ["*.md", "*.rst", "_autosummary/*"]
templates_path = ["_templates"]
# Modules whose API page only links to the guide page that documents them in full
autosummary_context = {
    "guide_pages": {"simulation.helper.configuration.configuration": "configuration"}
}

add_module_names = False
autodoc_member_order = "bysource"
autodoc_default_options = {
    "ignore-module-all": True,
    "members": True,
    "show-inheritance": True,
}
# Optional or unlisted dependencies plus the Cython extension a cached editable install can miss
autodoc_mock_imports = ["pyomo", "simulation.environment.cython_ext"]
napoleon_google_docstring = False
# Attributes sections list properties and dataclass fields that autodoc documents anyway
napoleon_use_ivar = True
napoleon_use_rtype = False
# Keeps return types linked once they share a line with the description
napoleon_preprocess_types = True

intersphinx_mapping = {
    "geopandas": ("https://geopandas.org/en/stable/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "pydantic": ("https://pydantic.dev/docs/validation/latest/", None),
    "python": ("https://docs.python.org/3/", None),
    "shapely": ("https://shapely.readthedocs.io/en/stable/", None),
    "simpy": ("https://simpy.readthedocs.io/en/latest/", None),
}
# A stalled docs host would otherwise block the CI job until the runner times out
intersphinx_timeout = 30

# autodoc_pydantic only hooks into the class-based autodoc, which Sphinx 9 keeps as legacy
autodoc_use_legacy_class_based = True
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_json = False

# README and CONTRIBUTING link to each other's sections by heading
myst_heading_anchors = 3
# The landing page cards use sphinx-design directives in ::: fences
myst_enable_extensions = ["colon_fence", "substitution"]
# enable markdown replacement of the version number in the docs, e.g. in the README
myst_substitutions = {"release": package_version}

html_theme = "pydata_sphinx_theme"
html_title = f"umosim {release}"
html_favicon = "_static/logo.svg"
html_show_copyright = False
html_show_sourcelink = False
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ["sidebar.js"]
# Top-level pages without pages below them would show an empty sidebar
html_sidebars = {"index": [], "CONTRIBUTING": [], "research": []}
html_theme_options = {
    "logo": {
        "text": "umosim",
        "image_light": "_static/logo.svg",
        "image_dark": "_static/logo-dark.svg",
    },
    # Opens the simulation package in the API reference sidebar
    "show_nav_level": 2,
    "navbar_end": ["version-switcher", "theme-switcher", "navbar-icon-links"],
    "switcher": {"json_url": switcher_json_url, "version_match": release},
    # The switcher list exists only in the build output, written by _write_switcher
    "check_switcher": False,
    "show_version_warning_banner": True,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/IS3UniCologne/urban-mobility-simulation",
            "icon": "fa-brands fa-github",
        }
    ],
    "use_edit_page_button": True,
}
html_context = {
    "github_user": "IS3UniCologne",
    "github_repo": "urban-mobility-simulation",
    "github_version": "develop",
    "doc_path": "docs",
}


def _check_pydantic_models(app: Sphinx, env: BuildEnvironment) -> None:
    objects = env.domains.python_domain.objects.values()
    if not any(entry.objtype == "pydantic_model" for entry in objects):
        logger.warning(
            "No Pydantic model rendered, autodoc_pydantic no longer hooks into autodoc"
        )


def _write_switcher(app: Sphinx, exception: Exception | None) -> None:
    """Write the version switcher list into the HTML output.

    The stable entry takes the package version.
    Develop keeps the version of the last release until Release Please merges the next one,
    so the list the develop build writes names the last release.
    """
    if exception is not None or app.builder.format != "html":
        return
    entries = [
        {"name": "develop", "version": "develop", "url": f"{_docs_url}/latest/"},
        {
            "name": "stable",
            "version": package_version,
            "url": f"{_docs_url}/stable/",
            "preferred": True,
        },
    ]
    switcher_path = Path(app.outdir, "_static", "switcher.json")
    switcher_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def setup(app: Sphinx) -> None:
    """Check the Pydantic rendering and write the version switcher list."""
    app.connect("env-check-consistency", _check_pydantic_models)
    app.connect("build-finished", _write_switcher)
