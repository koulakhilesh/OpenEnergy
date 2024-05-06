## Simulate API

### Endpoint

`GET /simulate`

### Description

This endpoint runs a simulation with the given parameters and returns the results.

### Query Parameters

- `battery_capacity` (float, optional): The capacity of the battery. Default is 1.0.
- `charge_efficiency` (float, optional): The charge efficiency of the battery. Default is 0.9.
- `discharge_efficiency` (float, optional): The discharge efficiency of the battery. Default is 0.9.
- `start_date` (string, optional): The start date of the simulation in the format `YYYY-MM-DD`. Default is `2015-02-01`.
- `end_date` (string, optional): The end date of the simulation in the format `YYYY-MM-DD`. Default is `2015-02-02`.
- `price_model` (string, optional): The price model to use for the simulation. Default is `SimulatedPriceModel`.
- `csv_path` (string, optional): The path to the CSV file with the time series data. Default is `data/time_series/time_series_60min_singleindex_filtered.csv`.
- `log_level` (string, optional): The log level. Default is `INFO`.

### Response

The response is a JSON array where each item is a dictionary with the following keys:

- `current_date`: The current date of the simulation.
- `schedule_df`: The schedule DataFrame as a dictionary.
- `daily_pnl`: The daily profit and loss.

### Example

Request:

```
GET /simulate?battery_capacity=1.0&charge_efficiency=0.9&discharge_efficiency=0.9&start_date=2015-02-01&end_date=2015-02-02&price_model=SimulatedPriceModel&csv_path=data/time_series/time_series_60min_singleindex_filtered.csv&log_level=INFO
```

Response:

```json
[
    {
        "current_date": "2015-02-01",
        "schedule_df": {
            // DataFrame data
        },
        "daily_pnl": 0.0
    },
    // More results
]
```

---
