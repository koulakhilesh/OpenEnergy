
# Energy Price Models Documentation

## ForecastPriceModel

The [`ForecastPriceModel`](command:_github.copilot.openSymbolInFile?%5B%22scripts%2Fprices%2Fforecasted_price.py%22%2C%22ForecastPriceModel%22%5D "scripts/prices/forecasted_price.py") class is a part of the energy price models. It implements the `IPriceData` and `IForecaster` interfaces. This model uses historical data and forecasting techniques to predict future energy prices.

### Key Methods

- [`__init__`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A9%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Initializes the model with a data provider, feature engineer, and a model. It also takes parameters for history length, forecast length, and whether to interpolate data.

- [`get_prices`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A36%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns a tuple of lists of float values representing the forecasted prices for a given date.

- [`train`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A78%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"): Trains the model on a given DataFrame with a specified column name.

- [`forecast`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fforecast%2F__init__.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A0%2C%22character%22%3A0%7D%5D "scripts/forecast/__init__.py"): Forecasts the prices based on a given DataFrame and a specified column name.

- [`evaluate`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A84%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"): Evaluates the model's performance based on the true and predicted values.

- [`save_model`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A87%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"): Saves the trained model to a specified file path.

- [`load_model`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A91%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"): Loads a trained model from a specified file path.

## HistoricalAveragePriceModel

The [`HistoricalAveragePriceModel`](command:_github.copilot.openSymbolInFile?%5B%22scripts%2Fprices%2Faverage_price.py%22%2C%22HistoricalAveragePriceModel%22%5D "scripts/prices/average_price.py") class is another energy price model. It implements the `IPriceData` interface. This model uses historical data to calculate the average energy prices.

### Key Methods

- [`__init__`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A9%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Initializes the model with a data provider and a boolean indicating whether to interpolate data.

- [`get_prices`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A36%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns a tuple of lists of float values representing the average prices for a given date.

- [`_get_current_date`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A48%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns the current date as a datetime object.

- [`_get_week_prior`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A53%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns the date one week prior to the current date.

- [`_get_last_week_data`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A56%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns the data for the last week.

- [`_get_average_prices_last_week`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A64%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns the average prices for the last week.

- [`_get_current_date_data`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A75%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns the data for the current date.

- [`_get_prices_current_date`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A78%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns the prices for the current date.

## SimulatedPriceModel

The [`SimulatedPriceModel`](command:_github.copilot.openSymbolInFile?%5B%22scripts%2Fprices%2Fsimulated_price.py%22%2C%22SimulatedPriceModel%22%5D "scripts/prices/simulated_price.py") class is a model that simulates energy prices. It implements the `IPriceData` interface. This model uses an envelope generator and a noise adder to simulate energy prices.

### Key Methods

- [`__init__`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A9%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Initializes the model with an envelope generator and a noise adder.

- [`get_prices`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A36%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py"): Returns a tuple of lists of float values representing the simulated prices for a given date.

## Supporting Classes

### IPriceData

[`IPriceData`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Finterfaces.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A5%2C%22character%22%3A6%7D%5D "scripts/prices/interfaces.py") is an interface that is implemented by all the price models. It defines the [`get_prices`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A36%2C%22character%22%3A8%7D%5D "scripts/prices/average_price.py") method that all price models must implement.

### IForecaster

[`IForecaster`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fforecast%2Fts_forecast.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A13%2C%22character%22%3A6%7D%5D "scripts/forecast/ts_forecast.py") is an interface that is implemented by the [`ForecastPriceModel`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A17%2C%22character%22%3A6%7D%5D "scripts/prices/forecasted_price.py"). It defines the [`train`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A78%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"), [`forecast`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fforecast%2F__init__.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A0%2C%22character%22%3A0%7D%5D "scripts/forecast/__init__.py"), [`evaluate`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A84%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"), [`save_model`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A87%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py"), and [`load_model`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A91%2C%22character%22%3A8%7D%5D "scripts/prices/forecasted_price.py") methods that the [`ForecastPriceModel`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fforecasted_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A17%2C%22character%22%3A6%7D%5D "scripts/prices/forecasted_price.py") must implement.

### IDataProvider

[`IDataProvider`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Finterfaces.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A23%2C%22character%22%3A6%7D%5D "scripts/prices/interfaces.py") is an interface that is implemented by the [`CSVDataProvider`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A8%2C%22character%22%3A6%7D%5D "scripts/prices/average_price.py") class. It defines the methods that a data provider must implement.

### CSVDataProvider

The [`CSVDataProvider`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Faverage_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A8%2C%22character%22%3A6%7D%5D "scripts/prices/average_price.py") class implements the [`IDataProvider`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Finterfaces.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A23%2C%22character%22%3A6%7D%5D "scripts/prices/interfaces.py") interface. It provides methods to read and process data from CSV files.

### IPriceEnvelopeGenerator

[`IPriceEnvelopeGenerator`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Finterfaces.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A11%2C%22character%22%3A6%7D%5D "scripts/prices/interfaces.py") is an interface that is implemented by the envelope generator used in the [`SimulatedPriceModel`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fsimulated_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A74%2C%22character%22%3A6%7D%5D "scripts/prices/simulated_price.py"). It defines the methods that an envelope generator must implement.

### IPriceNoiseAdder

[`IPriceNoiseAdder`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Finterfaces.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A17%2C%22character%22%3A6%7D%5D "scripts/prices/interfaces.py") is an interface that is implemented by the noise adder used in the [`SimulatedPriceModel`](command:_github.copilot.openSymbolFromReferences?%5B%7B%22%24mid%22%3A1%2C%22path%22%3A%22%2Fc%3A%2FUsers%2Fkoula%2FDocuments%2FGitHub%2FOpenEnergy%2Fscripts%2Fprices%2Fsimulated_price.py%22%2C%22scheme%22%3A%22file%22%7D%2C%7B%22line%22%3A74%2C%22character%22%3A6%7D%5D "scripts/prices/simulated_price.py"). It defines the methods that a noise adder must implement.