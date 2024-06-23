import pickle
import warnings
from abc import ABC, abstractmethod

import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from tqdm.auto import tqdm
from xgboost import XGBRegressor

from .interfaces import IEvaluator, IForecaster, ILoader, IModel, ISaver
from .ts_feature_engineering import DataPreprocessor

warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


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

    def fit(self, X, y, eval_set=None, early_stopping_rounds=None, sample_weight=None):
        super(MultiOutputRegressor, self)._validate_data(
            X, y, multi_output=True, accept_sparse="csc", dtype="numeric"
        )
        if y.ndim == 1:
            raise ValueError("y must be 2-dimensional")

        self.estimators_ = []
        for i in tqdm(range(y.shape[1])):
            e = clone(self.estimator)
            single_eval_set = (
                [(eval_set[0][0], eval_set[0][1][:, i])]
                if eval_set is not None
                else None
            )
            e = e.fit(
                X,
                y[:, i],
                eval_set=single_eval_set,
                early_stopping_rounds=early_stopping_rounds,
                sample_weight=sample_weight,
                verbose=100,
            )
            self.estimators_.append(e)

        return self


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
                "objective": "reg:squarederror",
            }

        self.model = ProgressMultiOutputRegressor(XGBRegressor(**params))

    def fit(self, X, y, eval_set=None, early_stopping_rounds=None):
        """
        Fits the XGBoost model to the given training data.

        Args:
            X: The input features for training.
            y: The target values for training.
            eval_set: The evaluation set for early stopping.
            early_stopping_rounds: The number of early stopping rounds.
        """

        self.model.fit(
            X, y, eval_set=eval_set, early_stopping_rounds=early_stopping_rounds
        )

    def predict(self, X):
        """
        Makes predictions using the trained XGBoost model.

        Args:
            X: The input features for making predictions.

        Returns:
            The predicted values.

        """
        return self.model.predict(X)



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

    def train(self, df, column_name, include_lead=True):
        """
        Trains the model using the input DataFrame and target column.

        Args:
            df (pandas.DataFrame): The input DataFrame.
            column_name (str): The name of the column to forecast.
            include_lead (bool): Whether to include lead features.
        """
        X, y = self.data_preprocessor.preprocess_data(
            df, column_name, include_lead=include_lead
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        eval_set = [(X_val, y_val)]
        self.model.fit(X_train, y_train, eval_set=eval_set, early_stopping_rounds=100)
        y_pred = self.model.predict(X_val)
        self.validation_mse = mean_squared_error(y_val, y_pred)
        print("Validation MSE:", self.validation_mse)

    def forecast(self, df, column_name, include_lead=False):
        """
        Performs forecasting on the input DataFrame and target column.

        Args:
            df (pandas.DataFrame): The input DataFrame.
            column_name (str): The name of the column to forecast.
            include_lead (bool): Whether to include lead features.

        Returns:
            array-like: The forecasted values.
        """
        assert (
            len(df) >= self.data_preprocessor.history_length
        ), "Input data must be at least history_length"

        # Feature engineer the dataframe
        df_engineered, X_columns, _ = self.data_preprocessor.feature_engineer.transform(
            df, column_name=column_name, include_lead=include_lead
        )

        X = df_engineered[X_columns].values

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
