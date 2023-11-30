import random


class Price:
    @staticmethod
    def load_random_price_data() -> list:
        """
        Generate random price data for simulation, for every 30 minutes.
        """
        prices = [random.uniform(10, 30) for _ in range(48)]
        return prices

    @staticmethod
    def load_placeholder_price_data():
        """
        Placeholder method for loading price data from an alternative source.
        """
        return [20 if i % 2 == 0 else 25 for i in range(48)]
