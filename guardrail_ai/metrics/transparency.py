import numpy as np


class SHAPExplainability:
    """
    Transparency metric using SHAP values.
    """

    @staticmethod
    def compute(shap_values: np.ndarray) -> float:

        if shap_values is None or len(shap_values) == 0:
            return 0.0

        shap_values = np.asarray(shap_values)

        # Mean absolute contribution
        mean_abs = np.mean(np.abs(shap_values)) / (np.max(np.abs(shap_values)) + 1e-6)

        # Distribution uniformity (entropy-like)
        abs_vals = np.abs(shap_values)
        total = np.sum(abs_vals)

        if total == 0:
            return 0.0

        probs = abs_vals / total
        entropy = -np.sum(probs * np.log(probs + 1e-9))

# FIX: prevent tiny negative due to float error
        max_entropy = np.log(len(abs_vals) + 1e-9)
        entropy = entropy / max_entropy
        score = mean_abs * entropy
        

       

        return float(score)