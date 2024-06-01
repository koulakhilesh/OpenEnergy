import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.multioutput import MultiOutputRegressor
import pickle
from xgboost import XGBRegressor
from sklearn.base import clone
from tqdm.auto import tqdm


from abc import ABC, abstractmethod

class IForecaster(ABC):

    @abstractmethod
    def train(self, df):
        pass

    @abstractmethod
    def forecast(self, df):
        pass

    @abstractmethod
    def evaluate(self, y_true, y_pred):
        pass

    @abstractmethod
    def save_model(self, file_path):
        pass

    @staticmethod
    @abstractmethod
    def load_model(file_path):
        pass

class ProgressMultiOutputRegressor(MultiOutputRegressor):
    def fit(self, X, y, sample_weight=None):
        super(MultiOutputRegressor, self)._validate_data(X, y, multi_output=True, accept_sparse="csc", dtype="numeric")
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
    def transform(self, df, column_name='value'):
        df = df.copy()
        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek
        df['rolling_mean'] = df[column_name].rolling(window=24).mean()
        df['rolling_min'] = df[column_name].rolling(window=24).min()
        df['rolling_max'] = df[column_name].rolling(window=24).max()
        df['rolling_std'] = df[column_name].rolling(window=24).std()
        df['diff_from_mean'] = df[column_name] - df['rolling_mean']
        return df.dropna()

class TimeSeriesForecaster(IForecaster):
    def __init__(self, model=XGBRegressor(random_state=42), feature_engineer=FeatureEngineer(), history_length=7*24, forecast_length=24):
        self.history_length = history_length
        self.forecast_length = forecast_length
        self.model = ProgressMultiOutputRegressor(model)
        self.feature_engineer = feature_engineer
        self.validation_mse = None

    def preprocess_data(self, df, column_name):
        assert len(df) >= self.history_length + self.forecast_length, "Input data must be at least history_length + forecast_length"
        df = self.feature_engineer.transform(df,column_name=column_name)
        X = np.array([df[i:i+self.history_length].values.ravel() for i in range(len(df)-self.history_length-self.forecast_length+1)])
        y = np.array([df[i+self.history_length:i+self.history_length+self.forecast_length][column_name] for i in range(len(df)-self.history_length-self.forecast_length+1)])
        return X, y

    def train(self, df, column_name):
        X, y = self.preprocess_data(df, column_name)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_val)
        self.validation_mse = mean_squared_error(y_val, y_pred)
        print('Validation MSE:', self.validation_mse)

    def forecast(self, df, column_name):
        assert len(df) >= self.history_length, "Input data must be at least history_length"
        df = self.feature_engineer.transform(df,column_name)
        X = df[-self.history_length:].values.ravel().reshape(1, -1)
        return self.model.predict(X)[0]

    def evaluate(self, y_true, y_pred):
        return mean_squared_error(y_true, y_pred)

    def save_model(self, file_path):
        with open(file_path, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load_model(file_path: str) -> 'TimeSeriesForecaster':
        try:
            with open(file_path, 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError):
            print(f"Failed to load model from {file_path}")