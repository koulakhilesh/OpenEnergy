import pickle
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from tqdm.auto import tqdm
from xgboost import XGBRegressor


class IForecaster(ABC):
    @abstractmethod
    def train(self, df):
        pass

    @abstractmethod
    def forecast(self, df):
        pass


class IEvaluator(ABC):
    @abstractmethod
    def evaluate(self, y_true, y_pred):
        pass


class ISaver(ABC):
    @abstractmethod
    def save_model(self, file_path):
        pass


class ILoader(ABC):
    @abstractmethod
    def load_model(self, file_path):
        pass


class ProgressMultiOutputRegressor(MultiOutputRegressor):
    def fit(self, X, y, sample_weight=None):
        super(MultiOutputRegressor, self)._validate_data(
            X, y, multi_output=True, accept_sparse="csc", dtype="numeric"
        )
        if y.ndim == 1:
            raise ValueError("y must be 2-dimensional")

        self.estimators_ = []
        for i in tqdm(range(y.shape[1])):
            e = clone(self.estimator)
            e = e.fit(X, y[:, i], sample_weight)
            self.estimators_.append(e)

        return self


class IFeatureEngineer(ABC):
    @abstractmethod
    def transform(self, df):
        pass


class FeatureEngineer(IFeatureEngineer):
    def __init__(self, window_size=24):
        self.window_size = window_size

    def transform(self, df, column_name="value"):
        df = df.copy()
        df = self.add_time_features(df)
        df = self.add_rolling_features(df, column_name)
        return df.dropna()

    def add_time_features(self, df):
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek
        return df

    def add_rolling_features(self, df, column_name):
        df["rolling_mean"] = df[column_name].rolling(window=self.window_size).mean()
        df["rolling_min"] = df[column_name].rolling(window=self.window_size).min()
        df["rolling_max"] = df[column_name].rolling(window=self.window_size).max()
        df["rolling_std"] = df[column_name].rolling(window=self.window_size).std()
        df["diff_from_mean"] = df[column_name] - df["rolling_mean"]
        return df


class IModel(ABC):
    @abstractmethod
    def fit(self, X, y):
        pass

    @abstractmethod
    def predict(self, X):
        pass


class XGBModel(IModel):
    def __init__(self):
        self.model = ProgressMultiOutputRegressor(XGBRegressor(random_state=42))

    def fit(self, X, y):
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)


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

    def preprocess_data(self, df, column_name):
        assert (
            len(df) >= self.history_length + self.forecast_length
        ), "Input data must be at least history_length + forecast_length"
        df = self.feature_engineer.transform(df, column_name=column_name)
        X = np.array(
            [
                df[i : i + self.history_length].values.ravel()
                for i in range(len(df) - self.history_length - self.forecast_length + 1)
            ]
        )
        y = np.array(
            [
                df[
                    i + self.history_length : i
                    + self.history_length
                    + self.forecast_length
                ][column_name]
                for i in range(len(df) - self.history_length - self.forecast_length + 1)
            ]
        )
        return X, y


class TimeSeriesForecaster(IForecaster, IEvaluator, ISaver, ILoader):
    def __init__(self, model: IModel, data_preprocessor: DataPreprocessor):
        self.model = model
        self.data_preprocessor = data_preprocessor
        self.validation_mse = None

    def train(self, df, column_name):
        X, y = self.data_preprocessor.preprocess_data(df, column_name)
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_val)
        self.validation_mse = mean_squared_error(y_val, y_pred)
        print("Validation MSE:", self.validation_mse)

    def forecast(self, df, column_name):
        assert (
            len(df) >= self.data_preprocessor.history_length
        ), "Input data must be at least history_length"
        df = self.data_preprocessor.feature_engineer.transform(df, column_name)
        X = df[-self.data_preprocessor.history_length :].values.ravel().reshape(1, -1)
        return self.model.predict(X)[0]

    def evaluate(self, y_true, y_pred):
        return mean_squared_error(y_true, y_pred)

    def save_model(self, file_path):
        with open(file_path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load_model(file_path: str) -> "TimeSeriesForecaster":
        try:
            with open(file_path, "rb") as f:
                return pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError):
            print(f"Failed to load model from {file_path}")
