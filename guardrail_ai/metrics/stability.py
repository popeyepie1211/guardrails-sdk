import numpy as np


class PSI:
    """
    Production-grade Population Stability Index (PSI)
    """

    @staticmethod
    def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    

        expected = np.asarray(expected)
        actual = np.asarray(actual)

    # Create bins from expected distribution
        bin_edges = np.histogram_bin_edges(expected, bins=bins)

    # Histogram counts
        expected_counts, _ = np.histogram(expected, bins=bin_edges)
        actual_counts, _ = np.histogram(actual, bins=bin_edges)

    # Convert to proportions
        expected_perc = expected_counts / len(expected)
        actual_perc = actual_counts / len(actual)

    # Avoid division by zero
        epsilon = 1e-6
        expected_perc = np.where(expected_perc == 0, epsilon, expected_perc)
        actual_perc = np.where(actual_perc == 0, epsilon, actual_perc)

    # PSI formula
        psi = np.sum((actual_perc - expected_perc) * np.log(actual_perc / expected_perc))

        return float(psi)