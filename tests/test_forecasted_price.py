import datetime
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))
from scripts.forecast.ts_forecast import IFeatureEngineer, IModel
from scripts.prices.forecasted_price import ForecastPriceModel
from scripts.shared.interfaces import IDataProvider


class MockDataProvider(IDataProvider):
    def get_data(self, column_names, timestamp_column):
        # Create a sample DataFrame
        df = pd.DataFrame(
            {
                "utc_timestamp": pd.date_range(
                    "2022-01-01", periods=300, freq="h", tz="UTC"
                ),
                "GB_GBN_price_day_ahead": np.arange(300),
            }
        )
        df.set_index("utc_timestamp", inplace=True)
        df.index.name = None
        return df


class MockFeatureEngineer(IFeatureEngineer):
    def transform(self, df, column_name):
        return df


class MockModel(IModel):
    def fit(self, X, y):
        pass

    def predict(self, X):
        return np.zeros((X.shape[0], 24))


def test_get_prices():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = MockFeatureEngineer()
    model = MockModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=7 * 24,
        forecast_length=24,
        interpolate=True,
    )

    # Get prices for a specific date
    date = datetime.date(2022, 1, 10)
    forecasted_prices, prices_current_date = forecast_model.get_prices(date)

    # Check the shape of the forecasted prices and prices for the current date
    assert len(forecasted_prices) == 24
    assert len(prices_current_date) == 24


def test_train():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = MockFeatureEngineer()
    model = MockModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=7 * 24,
        forecast_length=24,
        interpolate=True,
    )

    # Create a sample DataFrame for training
    df = pd.DataFrame(
        {
            "utc_timestamp": pd.date_range(
                "2022-01-01", periods=300, freq="h", tz="UTC"
            ),
            "GB_GBN_price_day_ahead": np.arange(300),
        }
    )

    # Train the model
    forecast_model.train(df)

    # Check if the model has been trained
    assert forecast_model.forecaster.validation_mse is not None


def test_forecast():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = MockFeatureEngineer()
    model = MockModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=7 * 24,
        forecast_length=24,
        interpolate=True,
    )

    # Create a sample DataFrame for forecasting
    df = pd.DataFrame(
        {
            "utc_timestamp": pd.date_range(
                "2022-01-01", periods=300, freq="h", tz="UTC"
            ),
            "GB_GBN_price_day_ahead": np.arange(300),
        }
    )

    # Forecast prices
    forecasted_prices = forecast_model.forecast(df)

    # Check the shape of the forecasted prices
    assert len(forecasted_prices) == 24


def test_evaluate():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = MockFeatureEngineer()
    model = MockModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=7 * 24,
        forecast_length=24,
        interpolate=True,
    )

    # Create dummy true and predicted values
    y_true = np.array([[1], [2], [3]])
    y_pred = np.array([[0], [0], [0]])

    # Evaluate the model
    mse = forecast_model.evaluate(y_true, y_pred)

    # Check the MSE value
    assert np.isclose(mse, 4.6667)


def test_save_model(tmp_path):
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = MockFeatureEngineer()
    model = MockModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=7 * 24,
        forecast_length=24,
        interpolate=True,
    )

    # Save the model
    file_path = tmp_path / "model.pkl"
    forecast_model.save_model(file_path)

    # Check if the model file exists
    assert file_path.exists()


def test_load_model(tmp_path):
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = MockFeatureEngineer()
    model = MockModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=7 * 24,
        forecast_length=24,
        interpolate=True,
    )

    # Save the model
    file_path = tmp_path / "model.pkl"
    forecast_model.save_model(file_path)

    # Load the model
    loaded_model = ForecastPriceModel.load_model(file_path)

    # Check if the loaded model is an instance of ForecastPriceModel
    assert isinstance(loaded_model, IModel)


if __name__ == "__main__":
    pytest.main()
