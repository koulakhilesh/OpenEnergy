import pandas as pd

from .interfaces import IDataProvider


class CSVDataProvider(IDataProvider):
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path

    def get_data(self, column_names: list, timestamp_column: str) -> pd.DataFrame:
        df = pd.read_csv(
            self.csv_file_path,
            parse_dates=[timestamp_column],
        )
        df = df.set_index(timestamp_column)
        df.index.name = None
        return df[column_names]
