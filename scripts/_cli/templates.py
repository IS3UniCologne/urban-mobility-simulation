"""Template discovery and scaffold substitution for project files."""

from __future__ import annotations

import ast
import re
import tomllib

from scripts._cli.paths import PRESETS_FILE, TEMPLATES_DIR
from scripts._cli.synthetic_demand import DemandParams


def _read_template(starter: str, filename: str) -> str:
    return (TEMPLATES_DIR / starter / filename).read_text()


def _extract_section(content: str, tag: str) -> str:
    pattern = re.compile(
        rf"^\s*#\s*SCAFFOLD:{tag}_START\s*\n(.*?)^\s*#\s*SCAFFOLD:{tag}_END\s*$",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(content)
    if match is None:
        raise ValueError(f"SCAFFOLD:{tag} markers not found in template")
    return match.group(1).strip("\n")


def _substitute_hex_inline(text: str, hexes: list[str]) -> str:
    hex_list = "[" + ", ".join(f'"{h}"' for h in hexes) + "]"
    pattern = re.compile(
        r"=\s*\[[^\]]*\]\s*#\s*SCAFFOLD:STATION_HEXES\s*$", re.MULTILINE
    )
    return pattern.sub(f"= {hex_list}", text)


def _merge_import_sections(sections: list[str]) -> str:
    """Merge import statements from multiple sections.

    When multiple operator templates are used in a single project, their import sections contain duplicate imports.
    This function merges them into a single section with unique imports.
    """
    module_to_names: dict[str, set[str]] = {}
    for section in sections:
        tree = ast.parse(section)
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                raise ValueError(
                    "Template IMPORTS section must contain only `from X import …` lines"
                )
            module_to_names.setdefault(node.module, set()).update(
                alias.name for alias in node.names
            )

    lines: list[str] = []
    for module in sorted(module_to_names):
        names = sorted(module_to_names[module])
        if len(names) == 1:
            lines.append(f"from {module} import {names[0]}")
        else:
            lines.append(f"from {module} import (")
            lines.extend(f"    {name}," for name in names)
            lines.append(")")

    return "\n".join(lines)


def build_operators_py(operator_types: list[str], station_hexes: list[str]) -> str:
    """Render ``operators.py`` from template.

    Parameters
    ----------
    operator_types : list of str
        Sequence of template names (e.g. ``["rh", "rh", "sm"]``).
    station_hexes : list of str
        H3 cells for station locations.

    Returns
    -------
    str
        Rendered Python source for ``operators.py``.
    """
    unique_types = list(dict.fromkeys(operator_types))
    templates = {t: _read_template(t, "operators.py") for t in unique_types}

    import_sections = [_extract_section(templates[t], "IMPORTS") for t in unique_types]
    vehicle_sections = [
        _extract_section(templates[t], "VEHICLE_DEFS") for t in unique_types
    ]
    operator_blocks = {
        t: _extract_section(templates[t], "OPERATOR") for t in unique_types
    }

    if len(unique_types) == 1:
        imports = import_sections[0]
    else:
        imports = _merge_import_sections(import_sections)

    vehicle_defs = _substitute_hex_inline(
        "\n\n\n".join(vehicle_sections), station_hexes
    )

    # Append commas to operator blocks and join them into the OPERATORS list.
    entries = "\n".join(
        operator_blocks[t].rstrip().rstrip(",") + "," for t in operator_types
    )
    operators_list = f"OPERATORS = [\n{entries}\n]"

    return (
        '"""Operator configuration."""\n\n'
        "from __future__ import annotations\n\n"
        f"{imports}\n\n\n"
        f"{vehicle_defs}\n\n\n"
        f"{operators_list}\n"
    )


def build_config_toml(dataset_name: str) -> str:
    """Render ``config.toml``from the shared template."""
    content = (TEMPLATES_DIR / "config.toml").read_text()
    return content.replace("__DATASET_NAME__", dataset_name)


def build_population_py() -> str:
    """Render ``population.py`` from the shared template."""
    return (TEMPLATES_DIR / "population.py").read_text()


def build_run_py(operator_types: list[str]) -> str:
    """Render ``run.py``.

    A project with exactly one operator whose starter ships its own ``run.py`` gets that one.
    Every other project gets the shared template, since a starter's runner may act for one operator only.

    Parameters
    ----------
    operator_types : list of str
        Sequence of template names (e.g. ``["rh", "rh", "sm"]``).
    """
    if (
        len(operator_types) == 1
        and (TEMPLATES_DIR / operator_types[0] / "run.py").exists()
    ):
        return _read_template(operator_types[0], "run.py")
    return (TEMPLATES_DIR / "run.py").read_text()


def load_presets() -> dict[str, tuple[float, float, float, float]]:
    """Load bounding box presets from the PRESETS_FILE.

    Returns
    -------
    dict
        Mapping of preset name to ``(lat_min, lon_min, lat_max, lon_max)``.
        Empty if the presets file is absent.
    """
    if not PRESETS_FILE.exists():
        return {}
    with open(PRESETS_FILE, "rb") as f:
        data = tomllib.load(f)
    presets: dict[str, tuple[float, float, float, float]] = {}
    for name, entry in data.items():
        bbox = entry["bbox"]
        if len(bbox) != 4:
            raise ValueError(f"Preset '{name}' has {len(bbox)} bbox values; expected 4")
        presets[name] = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    return presets


def load_preset_demand_params(name: str) -> DemandParams:
    """Return the ``DemandParams`` for a preset's optional ``[<name>.demand]`` table.

    Parameters
    ----------
    name : str
        Preset name as it appears in ``scripts/_presets.toml``.

    Returns
    -------
    DemandParams
        Parsed demand modifiers for the preset or default fallback.
    """
    if not PRESETS_FILE.exists():
        return DemandParams()
    with open(PRESETS_FILE, "rb") as f:
        data = tomllib.load(f)
    demand_table = data.get(name, {}).get("demand", {})
    return DemandParams.from_mapping(demand_table)


def list_starters() -> list[str]:
    """Return sorted list of operator-type codes for which a template exists."""
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir())
