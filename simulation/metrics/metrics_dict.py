"""Module for MetricsDict class, a dictionary subclass for simulation metrics."""

import csv
import logging
import os
from datetime import datetime

import pandas as pd
from prettytable import PrettyTable


class MetricsDict(dict[str, object]):
    """
    Dictionary subclass for simulation metrics with some convenience methods.

    Methods
    -------
    to_log(logger=None, prefix="")
        Recursively log the metrics using the logging module.
    to_file(file_name=None, file_format="csv")
        Save the metrics dictionary to a file.
    """

    def to_file(self, file_name: str | None, file_format: str = "csv") -> None:
        """
        Save the metrics dictionary to a file.

        Parameters
        ----------
        file_name : str
            Filename for the output file.
        file_format : str
            Format to save the file in. Supported formats: "csv", "parquet".
        """
        if file_name is None:
            raise ValueError("file_name must be provided")
        if not file_name.endswith(f".{file_format}"):
            file_name += f".{file_format}"

        output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        name_without_ext, ext = os.path.splitext(file_name)
        file_name = f"{name_without_ext}_{output_timestamp}{ext}"

        # Ensure the directory exists
        file_path = os.path.dirname("data/output/" + "metrics/")
        os.makedirs(file_path, exist_ok=True)

        full_path = os.path.join(file_path, file_name)

        if file_format == "csv":
            with open(full_path, mode="w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                for key, value in self.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            writer.writerow([f"{key}.{sub_key}", sub_value])
                    else:
                        writer.writerow([key, value])
        elif file_format == "parquet":
            flattened_data = self.flatten()
            df = pd.DataFrame(
                [
                    {"metric_name": key, "metric_value": value}
                    for key, value in flattened_data.items()
                ]
            )
            df.to_parquet(full_path, index=False)

    def to_log(self, logger: logging.Logger | None = None, prefix: str = "") -> None:
        """
        Log the metrics dictionary.

        If the dictionary contains nested dictionaries, it will log them recursively.
        We use PrettyTable for better formatting.

        Parameters
        ----------
        logger : logging.Logger or None
            Logger to use. If None, uses the root logger.
        prefix : str
            Prefix for nested keys.
        """
        if logger is None:
            logger = logging.getLogger()

        # If we have multiple items and they're all scalars, use table format
        scalar_items = {k: v for k, v in self.items() if not isinstance(v, dict)}
        dict_items = {k: v for k, v in self.items() if isinstance(v, dict)}

        # Handle scalar items as a table if there are multiple
        if scalar_items and len(scalar_items) > 1:
            table = PrettyTable()
            table.field_names = ["Metric", "Value"]
            table.align["Metric"] = "r"
            table.align["Value"] = "l"

            for key, value in scalar_items.items():
                if isinstance(value, float):
                    value_str = f"{value:,.2f}"
                elif isinstance(value, int):
                    value_str = f"{value:,}"
                else:
                    value_str = str(value)
                table.add_row([key, value_str])

            logger.info("%sMETRICS:\n%s", prefix, table.get_string())
        elif scalar_items and len(scalar_items) == 1:
            # Single scalar item - log individually
            for key, value in scalar_items.items():
                if isinstance(value, float):
                    value_str = f"{value:,.2f}"
                elif isinstance(value, int):
                    value_str = f"{value:,}"
                else:
                    value_str = str(value)
                logger.info("%s%s: %s", prefix, key, value_str)

        for key, value in dict_items.items():
            table = PrettyTable()
            table.field_names = ["Metric", "Value"]
            table.align["Metric"] = "r"
            table.align["Value"] = "l"

            for sub_key, sub_value in value.items():
                if isinstance(sub_value, dict):
                    # For nested dictionaries we use recursion
                    if isinstance(sub_value, MetricsDict):
                        sub_value.to_log(logger, f"{prefix}{key}.{sub_key}.")
                    else:
                        MetricsDict(sub_value).to_log(
                            logger, f"{prefix}{key}.{sub_key}."
                        )
                else:
                    if isinstance(sub_value, float):
                        value_str = f"{sub_value:,.2f}"
                    elif isinstance(sub_value, int):
                        value_str = f"{sub_value:,}"
                    else:
                        value_str = str(sub_value)
                    table.add_row([sub_key, value_str])

            if table.rowcount > 0:
                logger.info(
                    "%s%s METRICS:\n%s", prefix, key.upper(), table.get_string()
                )

    def flatten(self, prefix: str = "") -> dict[str, object]:
        """
        Flatten nested dictionary to single level with dot-separated keys.

        This is used for exporting metrics data in a flat format.

        Parameters
        ----------
        prefix : str
            Prefix for keys.

        Returns
        -------
        dict[str, object]
            Flattened dictionary with dot-separated keys.
        """
        result = {}

        for key, value in self.items():
            full_key = f"{prefix}{key}" if prefix else key

            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                if isinstance(value, MetricsDict):
                    result.update(value.flatten(f"{full_key}."))
                else:
                    result.update(MetricsDict(value).flatten(f"{full_key}."))
            else:
                result[full_key] = value

        return result
