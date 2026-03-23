from typing import Dict, Any
import pandas as pd
import numpy as np

class StatisticalParity:
    """
    Computes Statistical Parity Difference.
    """

    @staticmethod
    def compute(
        df: pd.DataFrame,
        prediction_column: str,
        protected_attributes: Dict[str, Any],
    ) -> float:
        """
        Computes maximum absolute statistical parity difference
        across protected groups.

        Returns:
            float: statistical parity difference
        """

        attr_type = protected_attributes["type"]
        columns = protected_attributes["columns"]

        # -----------------------------
        # Categorical Case
        # -----------------------------
        if attr_type == "categorical":

            col = columns[0]

            group_rates = (
                df.groupby(col)[prediction_column]
                .mean()
                .to_dict()
            )

        # -----------------------------
        # One-Hot Case
        # -----------------------------
        elif attr_type == "one_hot":

            group_rates = {}

            for col in columns:
                mask = df[col] == 1
                if mask.sum() == 0:
                    continue

                group_rates[col] = df.loc[mask, prediction_column].mean()

        else:
            raise ValueError("Invalid protected attribute type.")

        if len(group_rates) < 2:
            return 0.0

        rates = list(group_rates.values())

        max_diff = 0.0

        for i in range(len(rates)):
            for j in range(i + 1, len(rates)):
                diff = abs(rates[i] - rates[j])
                max_diff = max(max_diff, diff)

        return float(max_diff)
    


class GiniCoefficient:
    """
    Computes Gini Coefficient for prediction inequality.
    """

    @staticmethod
    def compute(predictions: np.ndarray) -> float:
        """
        Compute Gini coefficient.

        Handles:
        - binary predictions
        - probability predictions
        - multiclass probabilities (converted to max confidence)

        Args:
            predictions (np.ndarray): model predictions

        Returns:
            float: gini coefficient
        """

        if len(predictions) == 0:
            return 0.0

        predictions = np.asarray(predictions)

        # -----------------------------
        # Handle multiclass probabilities
        # -----------------------------
        if predictions.ndim == 2:
            predictions = np.max(predictions, axis=1)

        # Flatten
        predictions = predictions.flatten()

        # All zeros
        if np.all(predictions == 0):
            return 0.0

        mean = np.mean(predictions)

        if mean == 0:
            return 0.0

        n = len(predictions)

        # Efficient pairwise difference computation
        diff_sum = np.abs(
            predictions[:, None] - predictions[None, :]
        ).sum()

        gini = diff_sum / (2 * n * n * mean)

        return float(gini)