import warnings

import pandas as pd

from .interfaces import IFeatureEngineer

warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


class FeatureEngineer(IFeatureEngineer):
    """
    FeatureEngineer is a class that performs feature engineering on time series data.

    Attributes:
        window_size (int): The size of the rolling window for calculating rolling features.
        lag (int): The lag value for creating lag features.
        lead (int): The lead value for creating lead features.
    """

    def __init__(self, window_size=24, lag=7 * 24, lead=24):
        self.window_size = window_size
        self.lag = lag
        self.lead = lead

    def transform(self, df, column_name="value", include_lead=True):
        """
        Transforms the input DataFrame by adding time, rolling, lag, and lead features.

        Args:
            df (pandas.DataFrame): The input DataFrame.
            column_name (str): The name of the column to calculate features on.
            include_lead (bool): Whether to include lead features.

        Returns:
            df (pandas.DataFrame): The transformed DataFrame.
            X_columns (list): The list of column names for the input features.
            y_columns (list): The list of column names for the target values.

        """
        df = df.copy()
        X_columns = [column_name]
        y_columns = []
        df, columns = self.add_time_features(df)
        X_columns.extend(columns)
        df, columns = self.add_rolling_features(df, column_name)
        X_columns.extend(columns)
        df, columns = self.add_lag_features(df, column_name, self.lag)
        X_columns.extend(columns)
        if include_lead:
            df, columns = self.add_lead_features(df, column_name, self.lead)
            y_columns.extend(columns)
        return df.dropna(), X_columns, y_columns

    def add_time_features(self, df):
        """
        Adds time features to the DataFrame.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.

        Returns:
        - df (pandas.DataFrame): The DataFrame with added time features.
        - columns (list): The list of column names for the time features.

        """
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek
        df["month"] = df.index.month
        df["day_of_month"] = df.index.day
        df["week_of_year"] = df.index.isocalendar().week
        df["is_weekend"] = (df.index.dayofweek > 4).astype(int)
        columns = [
            "hour",
            "day_of_week",
            "month",
            "day_of_month",
            "week_of_year",
            "is_weekend",
        ]
        return df, columns

    def add_rolling_features(self, df, column_name):
        """
        Adds rolling features to the DataFrame.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.
        - column_name (str): The name of the column to calculate rolling features on.

        Returns:
        - df (pandas.DataFrame): The DataFrame with added rolling features.
        - columns (list): The list of column names for the rolling features.
        """

        df["rolling_mean"] = df[column_name].rolling(window=self.window_size).mean()
        df["rolling_min"] = df[column_name].rolling(window=self.window_size).min()
        df["rolling_max"] = df[column_name].rolling(window=self.window_size).max()
        df["rolling_std"] = df[column_name].rolling(window=self.window_size).std()
        df["rolling_skew"] = df[column_name].rolling(window=self.window_size).skew()
        df["rolling_median"] = df[column_name].rolling(window=self.window_size).median()
        df["rolling_quantile_25"] = (
            df[column_name].rolling(window=self.window_size).quantile(0.25)
        )
        df["rolling_quantile_75"] = (
            df[column_name].rolling(window=self.window_size).quantile(0.75)
        )
        columns = [
            "rolling_mean",
            "rolling_min",
            "rolling_max",
            "rolling_std",
            "rolling_skew",
            "rolling_median",
            "rolling_quantile_25",
            "rolling_quantile_75",
        ]
        return df, columns

    def add_lag_features(self, df, column_name, lag):
        """
        Adds lag features to the DataFrame.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.
        - column_name (str): The name of the column to create lag features for.
        - lag (int): The number of lag values to add.

        Returns:
        - df (pandas.DataFrame): The DataFrame with added lag features.
        - columns (list): The list of column names for the lag features.

        """
        for i in range(1, lag):
            df[f"{column_name}_lag_{i}"] = df[column_name].shift(i)

        columns = [f"{column_name}_lag_{i}" for i in range(1, lag)]
        return df, columns

    def add_lead_features(self, df, column_name, lead):
        """
        Adds lead features to the DataFrame.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.
        - column_name (str): The name of the column to create lead features for.
        - lead (int): The number of lead values to add.

        Returns:
        - df (pandas.DataFrame): The DataFrame with added lead features.
        - columns (list): The list of column names for the lead features.

        """
        for i in range(1, lead + 1):
            df[f"{column_name}_lead_{i}"] = df[column_name].shift(-i)

        columns = [f"{column_name}_lead_{i}" for i in range(1, lead + 1)]
        return df, columns


class DataPreprocessor:
    def __init__(
        self,
        feature_engineer: IFeatureEngineer,
        history_length=7 * 24,
        forecast_length=24,
    ):
        self.history_length = history_length
        self.forecast_length = forecast_length
        self.feature_engineer = feature_engineer

    def preprocess_data(self, df, column_name, include_lead=True):
        """
        Preprocesses the input data by performing feature engineering.

        Args:
            df (pandas.DataFrame): The input DataFrame.
            column_name (str): The name of the column to forecast.
            include_lead (bool): Whether to include lead features.

        Returns:
            X (array-like): The input features.
            y (array-like): The target values.
        """

        assert (
            len(df) >= self.history_length + self.forecast_length
        ), "Input data must be at least history_length + forecast_length"

        df_engineered, X_columns, y_columns = self.feature_engineer.transform(
            df, column_name=column_name, include_lead=include_lead
        )

        X = df_engineered[X_columns].values
        y = df_engineered[y_columns].values

        return X, y
