import random


class PriceSimulator:
    """
    A class representing price data for simulation.
    """

    @staticmethod
    def load_random_price_data(num_intervals=48, min_price=10, max_price=30) -> list:
        """
        Generate random price data for simulation, for specified intervals.

        Parameters:
        - num_intervals (int): The number of price intervals to generate.
        - min_price (float): The minimum price value.
        - max_price (float): The maximum price value.

        Returns:
        List[float]: A list of randomly generated prices.
        """
        prices = [random.uniform(min_price, max_price) for _ in range(num_intervals)]
        return prices

    @staticmethod
    def load_placeholder_price_data(
        num_intervals=48, even_price=20, odd_price=25
    ) -> list:
        """
        Generate placeholder price data for simulation.

        Parameters:
        - num_intervals (int): The number of price intervals.
        - even_price (float): The price for even intervals.
        - odd_price (float): The price for odd intervals.

        Returns:
        List[float]: A list of placeholder prices.
        """
        return [even_price if i % 2 == 0 else odd_price for i in range(num_intervals)]
