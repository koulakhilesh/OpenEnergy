import datetime
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)
from scripts.forecast.ts_feature_engineering import FeatureEngineer
from scripts.forecast.ts_forecast import IModel, XGBModel
from scripts.price_models.forecasted_price_model import ForecastPriceModel
from scripts.shared.interfaces import IDataProvider


class MockDataProvider(IDataProvider):
    def get_data(self, column_names, timestamp_column):
        # Create a sample DataFrame
        df = pd.DataFrame(
            {
                "utc_timestamp": pd.date_range(
                    "2022-01-01", periods=96, freq="h", tz="UTC"
                ),
                "GB_GBN_price_day_ahead": np.arange(96),
            }
        )
        df.set_index("utc_timestamp", inplace=True)
        df.index.name = None
        return df


def test_get_prices():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = FeatureEngineer(window_size=24, lag=24, lead=24)
    model = XGBModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=24,
        forecast_length=24,
        interpolate=True,
        prior_days=1,
    )
    # train the model
    full_data = data_provider.get_data("GB_GBN_price_day_ahead", "utc_timestamp")
    train_data = full_data.loc[full_data.index.day < 4]
    forecast_model.train(train_data)

    # Get prices for a specific date
    date = datetime.date(2022, 1, 4)
    forecasted_prices, prices_current_date = forecast_model.get_prices(date)

    # Check the shape of the forecasted prices and prices for the current date
    assert len(forecasted_prices) == 24
    assert len(prices_current_date) == 24


def test_train():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = FeatureEngineer(window_size=24, lag=24, lead=24)
    model = XGBModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=24,
        forecast_length=24,
        interpolate=True,
        prior_days=1,
    )

    # train the model
    full_data = data_provider.get_data("GB_GBN_price_day_ahead", "utc_timestamp")
    train_data = full_data.loc[full_data.index.day < 4]

    # Train the model
    forecast_model.train(train_data)

    # Check if the model has been trained
    assert forecast_model.forecaster.validation_mse is not None


def test_forecast():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = FeatureEngineer(window_size=24, lag=24, lead=24)
    model = XGBModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=24,
        forecast_length=24,
        interpolate=True,
        prior_days=1,
    )

    # train the model
    full_data = data_provider.get_data("GB_GBN_price_day_ahead", "utc_timestamp")
    train_data = full_data.loc[full_data.index.day < 4]
    forecast_model.train(train_data)

    # test_data
    test_df = full_data.loc[full_data.index.day == 4]

    # Forecast prices
    forecasted_prices = forecast_model.forecast(test_df)

    # Check the shape of the forecasted prices
    assert len(forecasted_prices) == 24


def test_evaluate():
    # Create a mock data provider, feature engineer, and model
    data_provider = MockDataProvider()
    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=3)
    model = XGBModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=3,
        forecast_length=3,
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
    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=3)
    model = XGBModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=3,
        forecast_length=3,
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
    feature_engineer = FeatureEngineer(window_size=3, lag=3, lead=3)
    model = XGBModel()

    # Create a ForecastPriceModel instance
    forecast_model = ForecastPriceModel(
        data_provider=data_provider,
        feature_engineer=feature_engineer,
        model=model,
        history_length=3,
        forecast_length=3,
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
    pytest.main([__file__])
