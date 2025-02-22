from abc import ABC, abstractmethod

import pandas as pd


class IDataProvider(ABC):
    @abstractmethod
    def get_data(self, column_names: list, timestamp_column: str) -> pd.DataFrame:
        pass
