import os
import sys

import pytest

sys.path.append(os.path.realpath(os.path.dirname(__file__) + "/.."))

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.mark.parametrize(
    "query_params, expected_status",
    [
        # Test the endpoint with valid arguments
        (
            {
                "battery_capacity": 10.0,
                "charge_efficiency": 0.9,
                "discharge_efficiency": 0.9,
                "start_date": "2015-02-01",
                "end_date": "2015-02-02",
                "price_model": "SimulatedPriceModel",
                "csv_path": "data/time_series/time_series_60min_singleindex_filtered.csv",
                "log_level": "INFO",
            },
            200,
        ),
        # Test the endpoint with missing arguments
        (
            {
                "charge_efficiency": 0.9,
                "discharge_efficiency": 0.9,
                "start_date": "2015-02-01",
                "end_date": "2015-02-02",
                "price_model": "SimulatedPriceModel",
                "csv_path": "data/time_series/time_series_60min_singleindex_filtered.csv",
                "log_level": "INFO",
            },
            200,
        ),
        # Test the endpoint when the simulation fails
        (
            {
                "battery_capacity": 1.0,
                "charge_efficiency": 0.9,
                "discharge_efficiency": 0.9,
                "start_date": "invalid_date",
                "end_date": "2015-02-02",
                "price_model": "SimulatedPriceModel",
                "csv_path": "data/time_series/time_series_60min_singleindex_filtered.csv",
                "log_level": "INFO",
            },
            500,
        ),
    ],
)
def test_simulate_endpoint(client, query_params, expected_status):
    # Test the endpoint with the provided query parameters
    response = client.get("/simulate", query_string=query_params)
    assert response.status_code == expected_status


if __name__ == "__main__":
    pytest.main()
