import numpy as np


class PSI:
    """
    Production-grade Population Stability Index (PSI)
    """

    @staticmethod
    def compute(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:

        if len(expected) == 0 or len(actual) == 0:
            return 0.0

        expected = np.asarray(expected)
        actual = np.asarray(actual)

        # -----------------------------
        # Handle constant expected
        # -----------------------------
        if np.all(expected == expected[0]):
            if np.all(actual == actual[0]) and expected[0] == actual[0]:
                return 0.0
            return 1.0

        # -----------------------------
        # Combine for stable binning
        # -----------------------------
        combined = np.concatenate([expected, actual])

        min_val = combined.min()
        max_val = combined.max()

        if min_val == max_val:
            return 0.0

        breakpoints = np.percentile(combined, np.linspace(0, 100, bins + 1))
        breakpoints = np.unique(breakpoints)

        # -----------------------------
        # Histogram
        # -----------------------------
        expected_counts = np.histogram(expected, bins=breakpoints)[0]
        actual_counts = np.histogram(actual, bins=breakpoints)[0]

        expected_perc = expected_counts / len(expected)
        actual_perc = actual_counts / len(actual)

        # -----------------------------
        # Avoid zeros
        # -----------------------------
        epsilon = 1e-6

        expected_perc = np.where(expected_perc == 0, epsilon, expected_perc)
        actual_perc = np.where(actual_perc == 0, epsilon, actual_perc)

        # -----------------------------
        # TRUE PSI (asymmetric)
        # -----------------------------
        psi = np.sum(
            (actual_perc - expected_perc) *
            np.log(actual_perc / expected_perc)
        )

        return float(psi)