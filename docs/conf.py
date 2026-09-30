"""Sphinx configuration for the urban-mobility-simulation documentation."""

from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING

from sphinx.util.logging import getLogger

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

logger = getLogger(__name__)

project = "urban-mobility-simulation"
release = metadata.version(project)

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
autodoc_mock_imports = [
    "keras",
    "pyomo",
    "simulation.environment.cython_ext",
    "tensorflow",
]
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
myst_enable_extensions = ["colon_fence"]

html_theme = "pydata_sphinx_theme"
html_title = f"umosim {release}"
html_favicon = "_static/logo.svg"
html_show_copyright = False
html_show_sourcelink = False
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ["sidebar.js"]
html_theme_options = {
    "logo": {
        "text": "umosim",
        "image_light": "_static/logo.svg",
        "image_dark": "_static/logo-dark.svg",
    },
    # Opens the simulation package in the API reference sidebar
    "show_nav_level": 2,
    "navbar_end": ["version-badge", "theme-switcher", "navbar-icon-links"],
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/IS3UniCologne/urban-mobility-simulation",
            "icon": "fa-brands fa-github",
        }
    ],
}


def _check_pydantic_models(app: Sphinx, env: BuildEnvironment) -> None:
    objects = env.domains.python_domain.objects.values()
    if not any(entry.objtype == "pydantic_model" for entry in objects):
        logger.warning(
            "No Pydantic model rendered, autodoc_pydantic no longer hooks into autodoc"
        )


def setup(app: Sphinx) -> None:
    """Fail the build when the configuration models lose their Pydantic rendering."""
    app.connect("env-check-consistency", _check_pydantic_models)
