import os
import sys
from configparser import ConfigParser
from pathlib import Path
from typing import Optional

import geopandas as gpd

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import Configuration

# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])


def load_geodesic_environment() -> GeodesicEnvironment:
    config = Configuration.instance()
    # Read Environment Files
    filename = config.bounding_box_file
    with open(filename, encoding="utf-8") as file:
        env_df = gpd.read_file(file)

    filename = config.env_layer_hex_9_file
    with open(filename, encoding="utf-8") as file:
        env_df_hex_9 = gpd.read_file(file, driver="GeoJSON")
        env_df_hex_9.set_index("hex_id_9", inplace=True)

    filename = config.env_layer_hex_8_file
    with open(filename, encoding="utf-8") as file:
        env_df_hex_8 = gpd.read_file(file)
        env_df_hex_8.set_index("hex_id_8", inplace=True)

    filename = config.env_layer_hex_7_file
    with open(filename, encoding="utf-8") as file:
        env_df_hex_7 = gpd.read_file(file)
        env_df_hex_7.set_index("hex_id_7", inplace=True)

    geodesic_environment = GeodesicEnvironment.getInstance()
    geodesic_environment.addLayer("bounding_box", env_df)
    geodesic_environment.addLayer("hex_9", env_df_hex_9)
    geodesic_environment.addLayer("hex_8", env_df_hex_8)
    geodesic_environment.addLayer("hex_7", env_df_hex_7)

    return geodesic_environment


def parse_multiline_list(
    section: str, key: str, delimiter: str, cast: Optional[type] = None
):
    multiline = (
        parser.get(section, key).replace("\n", "").replace(" ", "").split(delimiter)
    )
    multiline = multiline[0] if len(multiline) == 1 else multiline
    if isinstance(multiline, list):
        return [cast(x) for x in multiline] if cast is not None else multiline
    else:
        return cast(multiline) if cast is not None else multiline
