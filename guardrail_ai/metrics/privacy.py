import pandas as pd


class PrivacyScore:
    """
    Anonymity-based privacy score using uniqueness (k-anonymity proxy).
    """

    @staticmethod
    def compute(df: pd.DataFrame, quasi_columns: list) -> float:
        """
        Computes privacy score.

        Score = 1 - (unique_records / total_records)

        Args:
            df (pd.DataFrame)
            quasi_columns (list)

        Returns:
            float
        """

        if df.empty:
            return 0.0

        grouped = df.groupby(quasi_columns).size()

        total = len(df)

        unique_records = (grouped == 1).sum()

        score = 1 - (unique_records / total)

        return float(score)