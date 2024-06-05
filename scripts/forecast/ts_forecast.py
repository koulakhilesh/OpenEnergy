import pickle
from abc import ABC, abstractmethod

import numpy as np
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
    """
    A multi-output regressor that tracks progress during fitting.

    This class extends the `MultiOutputRegressor` class and adds progress tracking functionality
    during the fitting process. It fits multiple estimators, one for each output, and keeps track
    of the progress using the `tqdm` library.

    Parameters:
    -----------
    estimator : object
        The base estimator to fit on each output separately.

    Attributes:
    -----------
    estimators_ : list
        List of fitted estimators, one for each output.

    Methods:
    --------
    fit(X, y, sample_weight=None)
        Fit the regressor to the training data.

    Returns:
    --------
    self : object
        Returns self.
    """

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
    """
    A class for feature engineering on time series data.

    Parameters:
    - window_size (int): The size of the rolling window for calculating rolling features. Default is 24.

    Methods:
    - transform(df, column_name="value"): Transforms the input DataFrame by adding time features and rolling features.
    - add_time_features(df): Adds time-related features to the DataFrame.
    - add_rolling_features(df, column_name): Adds rolling features to the DataFrame.

    """

    def __init__(self, window_size=24):
        self.window_size = window_size

    def transform(self, df, column_name="value"):
        """
        Transforms the input DataFrame by adding time features and rolling features.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.
        - column_name (str): The name of the column to calculate rolling features on. Default is "value".

        Returns:
        - transformed_df (pandas.DataFrame): The transformed DataFrame with added features.

        """
        df = df.copy()
        df = self.add_time_features(df)
        df = self.add_rolling_features(df, column_name)
        return df.dropna()

    def add_time_features(self, df):
        """
        Adds time-related features to the DataFrame.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.

        Returns:
        - df (pandas.DataFrame): The DataFrame with added time features.

        """
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek
        return df

    def add_rolling_features(self, df, column_name):
        """
        Adds rolling features to the DataFrame.

        Parameters:
        - df (pandas.DataFrame): The input DataFrame.
        - column_name (str): The name of the column to calculate rolling features on.

        Returns:
        - df (pandas.DataFrame): The DataFrame with added rolling features.

        """
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
    """
    XGBModel is a class that represents an XGBoost model for forecasting.

    Attributes:
        model: The underlying XGBoost regressor model.

    Methods:
        fit(X, y): Fits the XGBoost model to the given training data.
        predict(X): Makes predictions using the trained XGBoost model.

    """

    def __init__(self, params=None):
        if params is None:
            params = {
                "random_state": 42,
                "n_estimators": 100,
                "max_depth": 5,
                "learning_rate": 0.1,
            }
        self.model = ProgressMultiOutputRegressor(XGBRegressor(**params))

    def fit(self, X, y):
        """
        Fits the XGBoost model to the given training data.

        Args:
            X: The input features for training.
            y: The target values for training.

        """
        self.model.fit(X, y)

    def predict(self, X):
        """
        Makes predictions using the trained XGBoost model.

        Args:
            X: The input features for making predictions.

        Returns:
            The predicted values.

        """
        return self.model.predict(X)


class DataPreprocessor:
    """
    A class that preprocesses data for time series forecasting.

    Args:
        feature_engineer (IFeatureEngineer): An instance of the feature engineer class.
        history_length (int): The length of the historical data used for forecasting. Default is 7 * 24.
        forecast_length (int): The length of the forecasted data. Default is 24.

    Attributes:
        history_length (int): The length of the historical data used for forecasting.
        forecast_length (int): The length of the forecasted data.
        feature_engineer (IFeatureEngineer): An instance of the feature engineer class.

    Methods:
        preprocess_data(df, column_name): Preprocesses the input data for time series forecasting.

    """

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
        """
        Preprocesses the input data for time series forecasting.

        Args:
            df (pandas.DataFrame): The input data as a pandas DataFrame.
            column_name (str): The name of the column to be forecasted.

        Returns:
            X (numpy.ndarray): The input features for forecasting.
            y (numpy.ndarray): The target values for forecasting.

        Raises:
            AssertionError: If the input data length is less than history_length + forecast_length.

        """
        assert (
            len(df) >= self.history_length + self.forecast_length
        ), "Input data must be at least history_length + forecast_length"
        X = np.array(
            [
                df[column_name][i : i + self.history_length].values.ravel()
                for i in range(len(df) - self.history_length - self.forecast_length + 1)
            ]
        )

        # Feature engineer the dataframe
        df_engineered = self.feature_engineer.transform(df, column_name=column_name)

        # Drop column_name from df_engineered
        df_engineered = df_engineered.drop(columns=[column_name])[: len(X)]

        # Add the feature engineered columns to X
        X = np.concatenate((X, df_engineered.values), axis=1)
        y = np.array(
            [
                df[column_name][
                    i + self.history_length : i
                    + self.history_length
                    + self.forecast_length
                ]
                for i in range(len(df) - self.history_length - self.forecast_length + 1)
            ]
        )
        return X, y


class TimeSeriesForecaster(IForecaster, IEvaluator, ISaver, ILoader):
    """
    A class that performs time series forecasting using a given model and data preprocessor.

    Args:
        model (IModel): The model used for forecasting.
        data_preprocessor (DataPreprocessor): The data preprocessor used for preprocessing the input data.

    Attributes:
        model (IModel): The model used for forecasting.
        data_preprocessor (DataPreprocessor): The data preprocessor used for preprocessing the input data.
        validation_mse (float): The mean squared error of the validation set.

    Methods:
        train(df, column_name): Trains the model using the input DataFrame and target column.
        forecast(df, column_name): Performs forecasting on the input DataFrame and target column.
        evaluate(y_true, y_pred): Evaluates the model's performance using the true and predicted values.
        save_model(file_path): Saves the model to a file.
        load_model(file_path): Loads a model from a file.

    """

    def __init__(self, model: IModel, data_preprocessor: DataPreprocessor):
        self.model = model
        self.data_preprocessor = data_preprocessor
        self.validation_mse = None

    def train(self, df, column_name):
        """
        Trains the model using the input DataFrame and target column.

        Args:
            df (pandas.DataFrame): The input DataFrame.
            column_name (str): The name of the target column.

        """
        X, y = self.data_preprocessor.preprocess_data(df, column_name)
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_val)
        self.validation_mse = mean_squared_error(y_val, y_pred)
        print("Validation MSE:", self.validation_mse)

    def forecast(self, df, column_name):
        """
        Performs forecasting on the input DataFrame and target column.

        Args:
            df (pandas.DataFrame): The input DataFrame.
            column_name (str): The name of the target column.

        Returns:
            float: The forecasted value.

        """
        assert (
            len(df) >= self.data_preprocessor.history_length
        ), "Input data must be at least history_length"

        # Create X using only df[column_name]
        X = np.array(
            [
                df[column_name][
                    i : i + self.data_preprocessor.history_length
                ].values.ravel()
                for i in range(len(df) - self.data_preprocessor.history_length + 1)
            ]
        )

        # Feature engineer the dataframe
        df_engineered = self.data_preprocessor.feature_engineer.transform(
            df, column_name=column_name
        )

        # Drop column_name from df_engineered
        df_engineered = df_engineered.drop(columns=[column_name])[: len(X)]

        # Add the feature engineered columns to X
        X = np.concatenate((X, df_engineered.values), axis=1)

        return self.model.predict(X)

    def evaluate(self, y_true, y_pred):
        """
        Evaluates the model's performance using the true and predicted values.

        Args:
            y_true (array-like): The true values.
            y_pred (array-like): The predicted values.

        Returns:
            float: The mean squared error.

        """
        return mean_squared_error(y_true, y_pred)

    def save_model(self, file_path):
        """
        Saves the model to a file.

        Args:
            file_path (str): The path to the file.

        """
        with open(file_path, "wb") as f:
            pickle.dump(self.model, f)

    @staticmethod
    def load_model(file_path: str) -> IModel:
        """
        Loads a model from a file.

        Args:
            file_path (str): The path to the file.

        Returns:
            IModel: The loaded model.

        Raises:
            FileNotFoundError: If the file is not found.
            pickle.UnpicklingError: If there is an error while unpickling the model.

        """
        try:
            with open(file_path, "rb") as f:
                return pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError) as e:
            print(f"Failed to load model from {file_path}")
            raise e
