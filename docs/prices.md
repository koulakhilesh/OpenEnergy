# Energy Price Models Documentation

This Python code defines several classes for generating and manipulating energy prices. These classes can be used to simulate energy prices in an energy market simulator.

## Classes

The code defines several interfaces and classes:

- `IPriceData`: This interface defines a method for getting energy prices for a given date.

- `IPriceEnvelopeGenerator`: This interface defines a method for generating a price envelope for a given date.

- `IPriceNoiseAdder`: This interface defines a method for adding noise to a list of prices.

- `IDataProvider`: This interface defines a method for getting data.

- `SimulatedPriceEnvelopeGenerator`: This class implements `IPriceEnvelopeGenerator`. It generates a price envelope for a given date using a sinusoidal function and some randomness.

- `SimulatedPriceNoiseAdder`: This class implements `IPriceNoiseAdder`. It adds noise to a list of prices by adding a random value to each price and occasionally adding a price spike.

- `SimulatedPriceModel`: This class implements `IPriceData`. It generates energy prices for a given date by generating a price envelope and then adding noise to it.

- `CSVDataProvider`: This class implements `IDataProvider`. It gets data from a CSV file.

- `HistoricalAveragePriceModel`: This class implements `IPriceData`. It calculates energy prices for a given date based on the historical average prices for the same day of the week.

## Usage

To use these classes, you need to create an instance of the class and call the appropriate methods. For example, to generate simulated energy prices for a given date, you can do the following:

```python
envelope_generator = SimulatedPriceEnvelopeGenerator()
noise_adder = SimulatedPriceNoiseAdder()
price_model = SimulatedPriceModel(envelope_generator, noise_adder)
prices = price_model.get_prices(date)
```

To get historical average prices for a given date, you can do the following:

```python
data_provider = CSVDataProvider(csv_file_path)
price_model = HistoricalAveragePriceModel(data_provider)
prices = price_model.get_prices(date)
```

The `get_prices` method returns a tuple of two lists of prices. The first list is the original prices (either the price envelope or the historical average prices), and the second list is the prices with noise and spikes added.