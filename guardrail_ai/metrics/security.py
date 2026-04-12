import numpy as np


class Security:
    """
    Security Metric:
    - L∞ Norm for adversarial robustness
    - OOD detection using mean/std
    """

    @staticmethod
    def linf_norm(expected: np.ndarray, actual: np.ndarray) -> float:
    

        if len(expected) == 0 or len(actual) == 0:
           return 0.0

        expected = np.asarray(expected)
        actual = np.asarray(actual)

        mean = np.mean(expected)
        std = np.std(expected) + 1e-6

        return float(np.max(np.abs(actual - mean)) / std)

    @staticmethod
    def ood_score(expected: np.ndarray, actual: np.ndarray, threshold: float = 3.0) -> float:
        """
        OOD score: percentage of points outside mean ± k*std
        """
        if len(expected) == 0 or len(actual) == 0:
            return 0.0

        expected = np.asarray(expected)
        actual = np.asarray(actual)

        mean = np.mean(expected)
        std = np.std(expected)

        if std == 0:
            return 0.0

        lower = mean - threshold * std
        upper = mean + threshold * std

        ood_count = np.sum((actual < lower) | (actual > upper))

        return float(ood_count / len(actual))

    @staticmethod
    def compute(expected: np.ndarray, actual: np.ndarray) -> dict:
        """
        Combined security metric
        """
        return {
            "linf": Security.linf_norm(expected, actual),
            "ood_score": Security.ood_score(expected, actual)
        }