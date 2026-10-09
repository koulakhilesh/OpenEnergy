import os
import sys
import datetime
import math
import random
from unittest.mock import Mock, patch
import pytest

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

from scripts.pv_generation_models.simulated_pv_model import (
    SimulatedPVGenerationEnvelopeGenerator,
    SimulatedPVGenerationNoiseAdder,
    SimulatedPVGenerationModel,
)
from scripts.pv_generation_models.interfaces import (
    IPVEnvelopeGenerator,
    IPVNoiseAdder,
    IPVData,
)


@pytest.fixture
def envelope_generator():
    """Fixture for envelope generator with default parameters."""
    return SimulatedPVGenerationEnvelopeGenerator()


@pytest.fixture
def custom_envelope_generator():
    """Fixture for envelope generator with custom parameters."""
    return SimulatedPVGenerationEnvelopeGenerator(
        num_intervals=48,
        min_generation=5.0,
        max_generation=150.0,
        peak_sun_hours_start=10.0,
        peak_sun_hours_end=18.0,
    )


@pytest.fixture
def noise_adder():
    """Fixture for noise adder with default parameters."""
    return SimulatedPVGenerationNoiseAdder()


@pytest.fixture
def custom_noise_adder():
    """Fixture for noise adder with custom parameters."""
    return SimulatedPVGenerationNoiseAdder(
        noise_level=20.0,
        spike_chance=0.05,
        spike_multiplier=3.0,
    )


@pytest.fixture
def simulated_pv_model(envelope_generator, noise_adder):
    """Fixture for simulated PV model."""
    return SimulatedPVGenerationModel(envelope_generator, noise_adder)


@pytest.fixture
def test_date():
    """Fixture for a standard test date."""
    return datetime.date(2024, 6, 15)


# Tests for SimulatedPVGenerationEnvelopeGenerator
class TestSimulatedPVGenerationEnvelopeGenerator:
    
    def test_initialization_default_params(self):
        """Test envelope generator initialization with default parameters."""
        generator = SimulatedPVGenerationEnvelopeGenerator()
        
        assert generator.num_intervals == 24
        assert generator.min_generation == 0.0
        assert generator.max_generation == 100.0
        assert generator.peak_sun_hours_start == 8.0
        assert generator.peak_sun_hours_end == 16.0

    @pytest.mark.parametrize(
        "num_intervals, min_gen, max_gen, peak_start, peak_end",
        [
            (12, 5.0, 80.0, 4.0, 8.0),
            (48, 10.0, 200.0, 10.0, 20.0),
            (24, 0.0, 150.0, 6.0, 18.0),
            (36, 2.5, 120.0, 9.0, 15.0),
        ],
    )
    def test_initialization_custom_params(self, num_intervals, min_gen, max_gen, peak_start, peak_end):
        """Test envelope generator initialization with custom parameters."""
        generator = SimulatedPVGenerationEnvelopeGenerator(
            num_intervals=num_intervals,
            min_generation=min_gen,
            max_generation=max_gen,
            peak_sun_hours_start=peak_start,
            peak_sun_hours_end=peak_end,
        )
        
        assert generator.num_intervals == num_intervals
        assert generator.min_generation == min_gen
        assert generator.max_generation == max_gen
        assert generator.peak_sun_hours_start == peak_start
        assert generator.peak_sun_hours_end == peak_end

    def test_generate_returns_correct_length(self, envelope_generator, test_date):
        """Test that generate returns list of correct length."""
        generations = envelope_generator.generate(test_date)
        
        assert isinstance(generations, list)
        assert len(generations) == envelope_generator.num_intervals
        assert all(isinstance(val, float) for val in generations)

    def test_generate_values_within_bounds(self, envelope_generator, test_date):
        """Test that generated values are within specified bounds."""
        generations = envelope_generator.generate(test_date)
        
        for gen in generations:
            assert envelope_generator.min_generation <= gen <= envelope_generator.max_generation

    def test_generate_deterministic_with_seed(self, envelope_generator):
        """Test that generate produces deterministic results for same date."""
        date1 = datetime.date(2024, 1, 1)
        date2 = datetime.date(2024, 1, 1)
        date3 = datetime.date(2024, 1, 2)
        
        gen1 = envelope_generator.generate(date1)
        gen2 = envelope_generator.generate(date2)
        gen3 = envelope_generator.generate(date3)
        
        # Same date should produce same results
        assert gen1 == gen2
        
        # Different date should produce different results
        assert gen1 != gen3

    def test_generate_peak_hours_higher_values(self, envelope_generator, test_date):
        """Test that peak sun hours produce higher values than off-peak hours."""
        generations = envelope_generator.generate(test_date)
        
        peak_start = int(envelope_generator.peak_sun_hours_start)
        peak_end = int(envelope_generator.peak_sun_hours_end)
        
        peak_values = generations[peak_start:peak_end]
        off_peak_values = generations[:peak_start] + generations[peak_end:]
        
        # Peak hours should generally have higher values
        avg_peak = sum(peak_values) / len(peak_values) if peak_values else 0
        avg_off_peak = sum(off_peak_values) / len(off_peak_values) if off_peak_values else 0
        
        assert avg_peak > avg_off_peak

    def test_generate_custom_intervals(self, custom_envelope_generator, test_date):
        """Test generation with custom number of intervals."""
        generations = custom_envelope_generator.generate(test_date)
        
        assert len(generations) == custom_envelope_generator.num_intervals
        assert all(
            custom_envelope_generator.min_generation <= gen <= custom_envelope_generator.max_generation
            for gen in generations
        )

    def test_interface_compliance(self, envelope_generator):
        """Test that envelope generator implements IPVEnvelopeGenerator interface."""
        assert isinstance(envelope_generator, IPVEnvelopeGenerator)
        assert hasattr(envelope_generator, 'generate')
        assert callable(envelope_generator.generate)

    @pytest.mark.parametrize(
        "test_date",
        [
            datetime.date(2024, 1, 1),   # New Year
            datetime.date(2024, 6, 21),  # Summer solstice
            datetime.date(2024, 12, 21), # Winter solstice
            datetime.date(2024, 2, 29),  # Leap year
            datetime.date(2000, 1, 1),   # Different millennium
        ],
    )
    def test_generate_various_dates(self, envelope_generator, test_date):
        """Test generation with various dates."""
        generations = envelope_generator.generate(test_date)
        
        assert len(generations) == envelope_generator.num_intervals
        assert all(isinstance(val, float) for val in generations)
        assert all(
            envelope_generator.min_generation <= gen <= envelope_generator.max_generation
            for gen in generations
        )


# Tests for SimulatedPVGenerationNoiseAdder
class TestSimulatedPVGenerationNoiseAdder:
    
    def test_initialization_default_params(self):
        """Test noise adder initialization with default parameters."""
        noise_adder = SimulatedPVGenerationNoiseAdder()
        
        assert noise_adder.noise_level == 10.0
        assert noise_adder.spike_chance == 0.02
        assert noise_adder.spike_multiplier == 2.0

    @pytest.mark.parametrize(
        "noise_level, spike_chance, spike_multiplier",
        [
            (5.0, 0.01, 1.5),
            (20.0, 0.05, 3.0),
            (15.0, 0.03, 2.5),
            (1.0, 0.001, 1.1),
        ],
    )
    def test_initialization_custom_params(self, noise_level, spike_chance, spike_multiplier):
        """Test noise adder initialization with custom parameters."""
        noise_adder = SimulatedPVGenerationNoiseAdder(
            noise_level=noise_level,
            spike_chance=spike_chance,
            spike_multiplier=spike_multiplier,
        )
        
        assert noise_adder.noise_level == noise_level
        assert noise_adder.spike_chance == spike_chance
        assert noise_adder.spike_multiplier == spike_multiplier

    def test_add_returns_correct_length(self, noise_adder):
        """Test that add returns list of same length as input."""
        input_generations = [10.0, 20.0, 30.0, 40.0, 50.0]
        noisy_generations = noise_adder.add(input_generations)
        
        assert isinstance(noisy_generations, list)
        assert len(noisy_generations) == len(input_generations)
        assert all(isinstance(val, float) for val in noisy_generations)

    def test_add_non_negative_values(self, noise_adder):
        """Test that add ensures all values are non-negative."""
        input_generations = [5.0, 10.0, 15.0, 20.0]
        noisy_generations = noise_adder.add(input_generations)
        
        # All values should be >= 0
        assert all(val >= 0.0 for val in noisy_generations)

    def test_add_with_zero_inputs(self, noise_adder):
        """Test noise addition with zero input values."""
        input_generations = [0.0, 0.0, 0.0, 0.0]
        noisy_generations = noise_adder.add(input_generations)
        
        assert len(noisy_generations) == len(input_generations)
        assert all(val >= 0.0 for val in noisy_generations)

    def test_add_empty_list(self, noise_adder):
        """Test noise addition with empty input list."""
        input_generations = []
        noisy_generations = noise_adder.add(input_generations)
        
        assert noisy_generations == []

    def test_add_modifies_values(self, noise_adder):
        """Test that noise addition actually modifies values."""
        # Use deterministic random seed for reproducible test
        random.seed(42)
        input_generations = [50.0, 60.0, 70.0, 80.0]
        
        random.seed(42)  # Reset seed
        noisy_generations = noise_adder.add(input_generations)
        
        # At least some values should be different (with high probability)
        differences = [abs(orig - noisy) for orig, noisy in zip(input_generations, noisy_generations)]
        assert any(diff > 0.01 for diff in differences)

    def test_interface_compliance(self, noise_adder):
        """Test that noise adder implements IPVNoiseAdder interface."""
        assert isinstance(noise_adder, IPVNoiseAdder)
        assert hasattr(noise_adder, 'add')
        assert callable(noise_adder.add)

    def test_add_with_spikes(self):
        """Test that spikes are occasionally added."""
        # Use high spike chance to ensure spikes occur
        high_spike_noise_adder = SimulatedPVGenerationNoiseAdder(
            noise_level=1.0,
            spike_chance=1.0,  # 100% chance of spikes
            spike_multiplier=2.0,
        )
        
        input_generations = [50.0] * 10
        
        random.seed(42)  # Deterministic for testing
        noisy_generations = high_spike_noise_adder.add(input_generations)
        
        # With 100% spike chance, all values should be significantly modified
        assert all(val != 50.0 for val in noisy_generations)


# Tests for SimulatedPVGenerationModel
class TestSimulatedPVGenerationModel:
    
    def test_initialization(self, envelope_generator, noise_adder):
        """Test model initialization."""
        model = SimulatedPVGenerationModel(envelope_generator, noise_adder)
        
        assert model.envelope_generator == envelope_generator
        assert model.noise_adder == noise_adder

    def test_get_generation_interface_compliance(self, simulated_pv_model, test_date):
        """Test that get_generation method works (interface compliance)."""
        gen_clean, gen_noisy = simulated_pv_model.get_generation(test_date)
        
        assert isinstance(gen_clean, list)
        assert isinstance(gen_noisy, list)
        assert len(gen_clean) == len(gen_noisy)
        assert len(gen_clean) == simulated_pv_model.envelope_generator.num_intervals

    def test_get_generations_returns_two_lists(self, simulated_pv_model, test_date):
        """Test that get_generations returns two lists."""
        gen_clean, gen_noisy = simulated_pv_model.get_generations(test_date)
        
        assert isinstance(gen_clean, list)
        assert isinstance(gen_noisy, list)
        assert len(gen_clean) == len(gen_noisy)
        assert len(gen_clean) == simulated_pv_model.envelope_generator.num_intervals

    def test_get_generations_calls_dependencies(self, test_date):
        """Test that get_generations calls envelope generator and noise adder."""
        mock_envelope_gen = Mock(spec=IPVEnvelopeGenerator)
        mock_noise_adder = Mock(spec=IPVNoiseAdder)
        
        expected_clean = [10.0, 20.0, 30.0]
        expected_noisy = [12.0, 18.0, 32.0]
        
        mock_envelope_gen.generate.return_value = expected_clean
        mock_noise_adder.add.return_value = expected_noisy
        
        model = SimulatedPVGenerationModel(mock_envelope_gen, mock_noise_adder)
        gen_clean, gen_noisy = model.get_generations(test_date)
        
        # Verify dependencies were called correctly
        mock_envelope_gen.generate.assert_called_once_with(date=test_date)
        mock_noise_adder.add.assert_called_once_with(expected_clean)
        
        # Verify results
        assert gen_clean == expected_clean
        assert gen_noisy == expected_noisy

    def test_get_generations_deterministic(self, simulated_pv_model):
        """Test that get_generations produces deterministic results for same date."""
        date = datetime.date(2024, 3, 15)
        
        gen1_clean, gen1_noisy = simulated_pv_model.get_generations(date)
        gen2_clean, gen2_noisy = simulated_pv_model.get_generations(date)
        
        # Clean generations should be identical (deterministic envelope)
        assert gen1_clean == gen2_clean
        
        # Noisy generations might be different due to random noise
        # but with the same seed, they should be the same too
        assert gen1_noisy == gen2_noisy

    def test_get_generations_different_dates(self, simulated_pv_model):
        """Test that different dates produce different results."""
        date1 = datetime.date(2024, 1, 1)
        date2 = datetime.date(2024, 6, 1)
        
        gen1_clean, gen1_noisy = simulated_pv_model.get_generations(date1)
        gen2_clean, gen2_noisy = simulated_pv_model.get_generations(date2)
        
        # Different dates should produce different results
        assert gen1_clean != gen2_clean
        assert gen1_noisy != gen2_noisy

    def test_interface_compliance(self, simulated_pv_model):
        """Test that model implements IPVData interface."""
        assert isinstance(simulated_pv_model, IPVData)
        assert hasattr(simulated_pv_model, 'get_generations')
        assert callable(simulated_pv_model.get_generations)

    @pytest.mark.parametrize(
        "test_date",
        [
            datetime.date(2024, 1, 1),   # New Year
            datetime.date(2024, 6, 21),  # Summer solstice
            datetime.date(2024, 12, 21), # Winter solstice
            datetime.date(2024, 2, 29),  # Leap year
            datetime.date(2000, 1, 1),   # Different millennium
        ],
    )
    def test_get_generations_various_dates(self, simulated_pv_model, test_date):
        """Test get_generations with various dates."""
        gen_clean, gen_noisy = simulated_pv_model.get_generations(test_date)
        
        assert len(gen_clean) == 24  # Default num_intervals
        assert len(gen_noisy) == 24
        assert all(isinstance(val, float) for val in gen_clean)
        assert all(isinstance(val, float) for val in gen_noisy)
        assert all(val >= 0.0 for val in gen_clean)
        assert all(val >= 0.0 for val in gen_noisy)


# Integration tests
class TestIntegration:
    
    def test_full_pipeline_integration(self):
        """Test the full pipeline with realistic parameters."""
        envelope_gen = SimulatedPVGenerationEnvelopeGenerator(
            num_intervals=24,
            min_generation=0.0,
            max_generation=100.0,
            peak_sun_hours_start=6.0,
            peak_sun_hours_end=18.0,
        )
        
        noise_adder = SimulatedPVGenerationNoiseAdder(
            noise_level=5.0,
            spike_chance=0.01,
            spike_multiplier=1.5,
        )
        
        model = SimulatedPVGenerationModel(envelope_gen, noise_adder)
        
        test_date = datetime.date(2024, 7, 15)  # Summer day
        gen_clean, gen_noisy = model.get_generations(test_date)
        
        # Verify basic properties
        assert len(gen_clean) == 24
        assert len(gen_noisy) == 24
        assert all(0.0 <= val <= 100.0 for val in gen_clean)
        assert all(val >= 0.0 for val in gen_noisy)
        
        # Verify peak sun hours have higher generation
        peak_hours = gen_clean[6:18]  # 6 AM to 6 PM
        off_peak_hours = gen_clean[:6] + gen_clean[18:]  # Night hours
        
        avg_peak = sum(peak_hours) / len(peak_hours)
        avg_off_peak = sum(off_peak_hours) / len(off_peak_hours) if off_peak_hours else 0
        
        assert avg_peak > avg_off_peak

    def test_edge_cases_boundary_values(self):
        """Test with edge case boundary values."""
        # Edge case: zero intervals returns empty list
        envelope_gen = SimulatedPVGenerationEnvelopeGenerator(num_intervals=0)
        generations = envelope_gen.generate(datetime.date(2024, 1, 1))
        assert generations == []
        assert len(generations) == 0
        
        # Edge case: single interval
        envelope_gen = SimulatedPVGenerationEnvelopeGenerator(num_intervals=1)
        generations = envelope_gen.generate(datetime.date(2024, 1, 1))
        assert len(generations) == 1
        
        # Edge case: min == max generation
        envelope_gen = SimulatedPVGenerationEnvelopeGenerator(
            min_generation=50.0,
            max_generation=50.0
        )
        generations = envelope_gen.generate(datetime.date(2024, 1, 1))
        assert all(val == 50.0 for val in generations)

    def test_realistic_pv_pattern(self):
        """Test that the generated pattern resembles realistic PV generation."""
        envelope_gen = SimulatedPVGenerationEnvelopeGenerator(
            num_intervals=24,
            min_generation=0.0,
            max_generation=100.0,
            peak_sun_hours_start=8.0,
            peak_sun_hours_end=16.0,
        )
        
        test_date = datetime.date(2024, 6, 15)  # Summer day
        generations = envelope_gen.generate(test_date)
        
        # Night hours (before 8 AM and after 4 PM) should have lower generation
        night_hours = generations[:8] + generations[16:]
        day_hours = generations[8:16]
        
        avg_night = sum(night_hours) / len(night_hours) if night_hours else 0
        avg_day = sum(day_hours) / len(day_hours) if day_hours else 0
        
        assert avg_day > avg_night
        
        # Should have some variation (not all values identical)
        assert len(set(generations)) > 1


if __name__ == "__main__":
    pytest.main([__file__])
