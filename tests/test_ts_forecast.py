import os
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_regression
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.forecast import (
    DataPreprocessor,
    FeatureEngineer,
    IModel,
    TimeSeriesForecaster,
    XGBModel,
)


def test_transform():
    # Create a sample DataFrame
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2022-01-01", periods=10, freq="h"),
            "value": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        }
    )
    df.set_index("timestamp", inplace=True)
    df.index.name = None

    # Create a FeatureEngineer instance
    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=2)

    # Apply the transform method
    transformed_df, X_columns, Y_columns = feature_engineer.transform(
        df, column_name="value", include_lead=True
    )

    # Check the shape of the transformed DataFrame
    assert transformed_df.shape == (6, 19)
    assert len(X_columns) == 17
    assert len(Y_columns) == 2

    # Check the values of the transformed DataFrame
    expected_values = np.array(
        [
            [
                3,
                2,
                5,
                1,
                1,
                52,
                1,
                2.0,
                1.0,
                3.0,
                1.0,
                6.394884621840883e-14,
                2.0,
                1.5,
                2.5,
                2.0,
                1.0,
                4.0,
                5.0,
            ],
            [
                4,
                3,
                5,
                1,
                1,
                52,
                1,
                3.0,
                2.0,
                4.0,
                1.0,
                -2.398081733190341e-14,
                3.0,
                2.5,
                3.5,
                3.0,
                2.0,
                5.0,
                6.0,
            ],
            [
                5,
                4,
                5,
                1,
                1,
                52,
                1,
                4.0,
                3.0,
                5.0,
                1.0,
                7.993605777301119e-15,
                4.0,
                3.5,
                4.5,
                4.0,
                3.0,
                6.0,
                7.0,
            ],
            [
                6,
                5,
                5,
                1,
                1,
                52,
                1,
                5.0,
                4.0,
                6.0,
                1.0,
                0.0,
                5.0,
                4.5,
                5.5,
                5.0,
                4.0,
                7.0,
                8.0,
            ],
            [
                7,
                6,
                5,
                1,
                1,
                52,
                1,
                6.0,
                5.0,
                7.0,
                1.0,
                0.0,
                6.0,
                5.5,
                6.5,
                6.0,
                5.0,
                8.0,
                9.0,
            ],
            [
                8,
                7,
                5,
                1,
                1,
                52,
                1,
                7.0,
                6.0,
                8.0,
                1.0,
                0.0,
                7.0,
                6.5,
                7.5,
                7.0,
                6.0,
                9.0,
                10.0,
            ],
        ]
    )
    np.testing.assert_array_equal(transformed_df.values, expected_values)


def test_xgb_model_fit():
    # Generate dummy data
    X, y = make_regression(n_samples=100, n_features=5, n_targets=3, random_state=42)

    # Fit the XGBModel
    model = XGBModel()
    model.fit(X, y)

    # Check if the model has been fitted
    assert model.model.estimators_ is not None


def test_xgb_model_predict():
    # Generate dummy data
    X, y = make_regression(n_samples=100, n_features=5, n_targets=3, random_state=42)

    # Fit the XGBModel
    model = XGBModel()
    model.fit(X, y)

    # Predict using the XGBModel
    X_test = np.random.randn(10, 5)
    y_pred = model.predict(X_test)

    # Check the shape of the predictions
    assert y_pred.shape == (10, 3)


def test_xgb_model_fit_predict_consistency():
    # Generate dummy data
    X, y = make_regression(n_samples=100, n_features=5, n_targets=3, random_state=42)

    # Split the data into train and validation sets
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Fit the XGBModel
    params = {"n_estimators": 10, "max_depth": 3, "random_state": 42}
    model = XGBModel(params)
    model.fit(X_train, y_train)

    # Predict using the XGBModel
    y_pred_fit = model.predict(X_val)

    # Fit and predict using the original MultiOutputRegressor
    original_regressor = MultiOutputRegressor(
        XGBRegressor(random_state=42, n_estimators=10, max_depth=3)
    )
    original_regressor.fit(X_train, y_train)
    y_pred_original = original_regressor.predict(X_val)

    # Check the consistency of predictions
    assert np.allclose(y_pred_fit, y_pred_original)


def test_xgb_model_evaluate():
    # Generate dummy data
    X, y = make_regression(n_samples=100, n_features=5, n_targets=3, random_state=42)

    # Split the data into train and validation sets
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Fit the XGBModel
    model = XGBModel()
    model.fit(X_train, y_train)

    # Predict using the XGBModel
    y_pred = model.predict(X_val)

    # Evaluate the model
    mse = mean_squared_error(y_val, y_pred)

    # Check if the MSE is a non-negative value
    assert mse >= 0


def test_preprocess_data():
    # Create a sample DataFrame
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2022-01-01", periods=10, freq="h"),
            "value": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        }
    )
    df.set_index("timestamp", inplace=True)
    df.index.name = None

    # Create a DataPreprocessor instance
    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=2)
    data_preprocessor = DataPreprocessor(
        feature_engineer=feature_engineer, history_length=3, forecast_length=2
    )

    # Preprocess the data
    X, y = data_preprocessor.preprocess_data(df, column_name="value")

    # Check the shape of X and y
    assert X.shape == (6, 17)
    assert y.shape == (6, 2)

    # Check the values of X and y
    expected_X = np.array(
        [
            [
                3,
                2,
                5,
                1,
                1,
                52,
                1,
                2.0,
                1.0,
                3.0,
                1.0,
                6.394884621840883e-14,
                2.0,
                1.5,
                2.5,
                2.0,
                1.0,
            ],
            [
                4,
                3,
                5,
                1,
                1,
                52,
                1,
                3.0,
                2.0,
                4.0,
                1.0,
                -2.398081733190341e-14,
                3.0,
                2.5,
                3.5,
                3.0,
                2.0,
            ],
            [
                5,
                4,
                5,
                1,
                1,
                52,
                1,
                4.0,
                3.0,
                5.0,
                1.0,
                7.993605777301119e-15,
                4.0,
                3.5,
                4.5,
                4.0,
                3.0,
            ],
            [6, 5, 5, 1, 1, 52, 1, 5.0, 4.0, 6.0, 1.0, 0.0, 5.0, 4.5, 5.5, 5.0, 4.0],
            [7, 6, 5, 1, 1, 52, 1, 6.0, 5.0, 7.0, 1.0, 0.0, 6.0, 5.5, 6.5, 6.0, 5.0],
            [8, 7, 5, 1, 1, 52, 1, 7.0, 6.0, 8.0, 1.0, 0.0, 7.0, 6.5, 7.5, 7.0, 6.0],
        ]
    )

    expected_y = np.array(
        [[4.0, 5.0], [5.0, 6.0], [6.0, 7.0], [7.0, 8.0], [8.0, 9.0], [9.0, 10.0]]
    )
    np.testing.assert_array_equal(X, expected_X)
    np.testing.assert_array_equal(y, expected_y)


def test_train():
    # Create a sample DataFrame
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2022-01-01", periods=10, freq="h"),
            "value": np.arange(10),
        }
    )

    df.set_index("timestamp", inplace=True)
    df.index.name = None

    # Create a mock model and data preprocessor
    model = XGBModel()
    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=2)
    data_preprocessor = DataPreprocessor(
        feature_engineer=feature_engineer, history_length=3, forecast_length=2
    )

    # Create a TimeSeriesForecaster instance
    forecaster = TimeSeriesForecaster(model, data_preprocessor)

    # Train the forecaster
    forecaster.train(df, column_name="value")

    # Check if the validation MSE is not None
    assert forecaster.validation_mse is not None


def test_forecast():
    # Create a sample DataFrame
    train_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2022-01-01", periods=10, freq="h"),
            "value": np.arange(10),
        }
    )
    train_df.set_index("timestamp", inplace=True)
    train_df.index.name = None

    test_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2022-01-14", periods=3, freq="h"),
            "value": np.arange(3),
        }
    )
    test_df.set_index("timestamp", inplace=True)
    test_df.index.name = None

    # Create a mock model and data preprocessor
    model = XGBModel()

    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=2)
    data_preprocessor = DataPreprocessor(
        feature_engineer=feature_engineer, history_length=3, forecast_length=2
    )

    # Create a TimeSeriesForecaster instance
    forecaster = TimeSeriesForecaster(model, data_preprocessor)
    forecaster.train(train_df, column_name="value")

    # Forecast using the forecaster
    forecast = forecaster.forecast(test_df, column_name="value")

    # Check the shape of the forecast
    assert forecast.shape == (1, 2)


def test_evaluate():
    # Create dummy true and predicted values
    y_true = np.array([[1, 2], [3, 4], [5, 6]])
    y_pred = np.array([[0, 0], [0, 0], [0, 0]])

    # Create a mock model and data preprocessor
    model = XGBModel()
    data_preprocessor = DataPreprocessor(FeatureEngineer())

    # Create a TimeSeriesForecaster instance
    forecaster = TimeSeriesForecaster(model, data_preprocessor)

    # Evaluate the forecaster
    mse = forecaster.evaluate(y_true, y_pred)

    # Check the MSE value
    assert np.isclose(mse, 15.1667)


def test_save_model(tmp_path):
    # Create a mock model and data preprocessor
    model = XGBModel()
    data_preprocessor = DataPreprocessor(FeatureEngineer())

    # Create a TimeSeriesForecaster instance
    forecaster = TimeSeriesForecaster(model, data_preprocessor)

    # Save the model
    file_path = tmp_path / "model.pkl"
    forecaster.save_model(file_path)

    # Check if the model file exists
    assert file_path.exists()


def test_load_model(tmp_path):
    # Create a mock model and data preprocessor
    model = XGBModel()
    data_preprocessor = DataPreprocessor(FeatureEngineer())

    # Create a TimeSeriesForecaster instance
    forecaster = TimeSeriesForecaster(model, data_preprocessor)

    # Save the model
    file_path = tmp_path / "model.pkl"
    forecaster.save_model(file_path)

    # Load the model
    loaded_forecaster = TimeSeriesForecaster.load_model(file_path)

    # Check if the loaded model is an instance of TimeSeriesForecaster
    assert isinstance(loaded_forecaster, IModel)


if __name__ == "__main__":
    pytest.main([__file__])
