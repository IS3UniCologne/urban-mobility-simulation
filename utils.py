import geopandas as gpd
import os

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import Configuration


# TODO: Why is this not part of the GeodesicEnvironment class?
def load_geodesic_environment() -> GeodesicEnvironment:
    config = Configuration()
    # Read Environment Files
    filename = os.path.normpath(config.path.PATH_ENV_BOUNDING_BOX)
    with open(filename, encoding="utf-8") as file:
        env_df = gpd.read_file(file)

    filename = os.path.normpath(config.path.PATH_ENV_HEX_LAYER_RES_9)
    with open(filename, encoding="utf-8") as file:
        env_df_hex_9 = gpd.read_file(file, driver="GeoJSON")
        env_df_hex_9.set_index("hex_id_9", inplace=True)

    filename = os.path.normpath(config.path.PATH_ENV_HEX_LAYER_RES_8)
    with open(filename, encoding="utf-8") as file:
        env_df_hex_8 = gpd.read_file(file)
        env_df_hex_8.set_index("hex_id_8", inplace=True)

    filename = os.path.normpath(config.path.PATH_ENV_HEX_LAYER_RES_7)
    with open(filename, encoding="utf-8") as file:
        env_df_hex_7 = gpd.read_file(file)
        env_df_hex_7.set_index("hex_id_7", inplace=True)

    geodesic_environment = GeodesicEnvironment.getInstance()
    geodesic_environment.addLayer("bounding_box", env_df)
    geodesic_environment.addLayer("hex_9", env_df_hex_9)
    geodesic_environment.addLayer("hex_8", env_df_hex_8)
    geodesic_environment.addLayer("hex_7", env_df_hex_7)

    return geodesic_environment
