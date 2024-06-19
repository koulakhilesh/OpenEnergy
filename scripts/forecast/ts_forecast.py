import pickle
from abc import ABC, abstractmethod

from sklearn.base import clone
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from tqdm.auto import tqdm
from xgboost import XGBRegressor

from .interfaces import IEvaluator, IForecaster, ILoader, IModel, ISaver


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


class IFeatureEngineer(ABC):
    @abstractmethod
    def transform(self, df, column_name, include_lead):
        pass


# TODO: Add lad and lead values as features
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
