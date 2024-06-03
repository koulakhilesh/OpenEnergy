import pandas as pd

from .interfaces import IDataProvider


class CSVDataProvider(IDataProvider):
    """
    A data provider that reads data from a CSV file.

    Args:
        csv_file_path (str): The path to the CSV file.

    Attributes:
        csv_file_path (str): The path to the CSV file.

    Methods:
        get_data(column_names: list, timestamp_column: str) -> pd.DataFrame:
            Reads the data from the CSV file and returns a DataFrame with the specified columns.

    """

    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path

    def get_data(self, column_names: list, timestamp_column: str) -> pd.DataFrame:
        """
        Reads the data from the CSV file and returns a DataFrame with the specified columns.

        Args:
            column_names (list): A list of column names to include in the DataFrame.
            timestamp_column (str): The name of the column to use as the index.

        Returns:
            pd.DataFrame: A DataFrame containing the specified columns from the CSV file.

        """
        df = pd.read_csv(
            self.csv_file_path,
            parse_dates=[timestamp_column],
        )
        df = df.set_index(timestamp_column)
        df.index.name = None
        return df[column_names]
