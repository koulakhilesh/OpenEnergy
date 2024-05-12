import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import pickle

from sklearn.base import clone


class TimeSeriesForecaster:
    def __init__(self, model=LinearRegression(), history_length=7*24, forecast_length=24):
        self.history_length = history_length
        self.forecast_length = forecast_length
        self.model = clone(model)

    def preprocess_data(self, df):
        assert len(df) >= self.history_length + self.forecast_length, "Input data must be at least history_length + forecast_length"
        X = np.array([df[i:i+self.history_length] for i in range(len(df)-self.history_length-self.forecast_length+1)])
        y = np.array([df[i+self.history_length:i+self.history_length+self.forecast_length] for i in range(len(df)-self.history_length-self.forecast_length+1)])
        return X, y

    def train(self, df):
        X, y = self.preprocess_data(df)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_val)
        print('Validation MSE:', mean_squared_error(y_val, y_pred))

    def forecast(self, df):
        assert len(df) >= self.history_length, "Input data must be at least history_length"
        X = df[-self.history_length:]
        return self.model.predict([X])[0]

    def evaluate(self, y_true, y_pred):
        return mean_squared_error(y_true, y_pred)

    def set_model(self, model):
        self.model = clone(model)

    def save_model(self, file_path):
        with open(file_path, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load_model(file_path):
        with open(file_path, 'rb') as f:
            return pickle.load(f)