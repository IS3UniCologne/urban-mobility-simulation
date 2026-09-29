"""Sphinx configuration for the urban-mobility-simulation documentation."""

from importlib import metadata

project = "urban-mobility-simulation"
release = metadata.version(project)

extensions = ["sphinx.ext.autodoc", "sphinx.ext.autosummary", "sphinx.ext.napoleon"]
exclude_patterns = ["_build"]

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

html_theme = "furo"
