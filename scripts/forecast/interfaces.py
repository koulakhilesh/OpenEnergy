from abc import ABC, abstractmethod


class IForecaster(ABC):
    """
    Interface for a forecaster.

    This interface defines the methods that a forecaster class should implement.

    Attributes:
        None

    Methods:
        train(df): Train the forecaster using the given dataframe.
        forecast(df): Generate forecasts using the trained model and the given dataframe.
    """

    @abstractmethod
    def train(self, df):
        """
        Train the forecaster using the given dataframe.

        Args:
            df (pandas.DataFrame): The training data.

        Returns:
            None
        """
        pass

    @abstractmethod
    def forecast(self, df):
        """
        Generate forecasts using the trained model and the given dataframe.

        Args:
            df (pandas.DataFrame): The data to generate forecasts for.

        Returns:
            pandas.DataFrame: The forecasted values.
        """
        pass


class IEvaluator(ABC):
    """Interface for evaluating model predictions."""

    @abstractmethod
    def evaluate(self, y_true, y_pred):
        """Evaluate the model predictions.

        Args:
            y_true: The true values.
            y_pred: The predicted values.
        """
        pass


class ISaver(ABC):
    """Interface for saving models."""

    @abstractmethod
    def save_model(self, file_path):
        """Save the model to the specified file path.

        Args:
            file_path (str): The path to save the model.

        Raises:
            NotImplementedError: If the method is not implemented by the subclass.
        """
        pass


class ILoader(ABC):
    """
    Abstract base class for model loaders.

    This class defines the interface for loading models from a file.

    Attributes:
        None

    Methods:
        load_model(file_path): Abstract method to load a model from a file.

    """

    @abstractmethod
    def load_model(self, file_path):
        pass


class IModel(ABC):
    """
    Abstract base class for machine learning models.

    This class defines the interface for all machine learning models.
    Subclasses must implement the `fit` and `predict` methods.

    Attributes:
        None

    Methods:
        fit(X, y): Fit the model to the training data.
        predict(X): Make predictions using the trained model.

    """

    @abstractmethod
    def fit(self, X, y):
        """
        Fit the model to the training data.

        Args:
            X: The input features.
            y: The target values.

        Returns:
            None

        """
        pass

    @abstractmethod
    def predict(self, X):
        """
        Make predictions using the trained model.

        Args:
            X: The input features.

        Returns:
            The predicted values.

        """
        pass
