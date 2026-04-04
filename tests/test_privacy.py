# import pandas as pd

# from guardrail_ai.metrics.privacy import PrivacyScore
# import pytest


# # -----------------------------
# # 1️⃣ Perfect Privacy (No Unique Rows)
# # -----------------------------
# def test_privacy_perfect_anonymity():
#     df = pd.DataFrame({
#         "age": [25, 25, 30, 30],
#         "zipcode": [12345, 12345, 67890, 67890],
#     })

#     result = PrivacyScore.compute(df, ["age", "zipcode"])

#     # No unique rows → full privacy
#     assert result == 1.0


# # -----------------------------
# # 2️⃣ Zero Privacy (All Unique)
# # -----------------------------
# def test_privacy_all_unique():
#     df = pd.DataFrame({
#         "age": [25, 26, 27, 28],
#         "zipcode": [11111, 22222, 33333, 44444],
#     })

#     result = PrivacyScore.compute(df, ["age", "zipcode"])

#     # All rows unique → no privacy
#     assert result == 0.0


# # -----------------------------
# # 3️⃣ Mixed Case
# # -----------------------------
# def test_privacy_mixed():
#     df = pd.DataFrame({
#         "age": [25, 25, 30, 31],
#         "zipcode": [12345, 12345, 67890, 99999],
#     })

#     result = PrivacyScore.compute(df, ["age", "zipcode"])

#     # 2 duplicate rows + 2 unique → score = 1 - (2/4) = 0.5
#     assert result == 0.5


# # -----------------------------
# # 4️⃣ Single Row Edge Case
# # -----------------------------
# def test_privacy_single_row():
#     df = pd.DataFrame({
#         "age": [25],
#         "zipcode": [12345],
#     })

#     result = PrivacyScore.compute(df, ["age", "zipcode"])

#     # Only one row → unique → no privacy
#     assert result == 0.0


# # -----------------------------
# # 5️⃣ Empty DataFrame
# # -----------------------------
# def test_privacy_empty():
#     df = pd.DataFrame(columns=["age", "zipcode"])

#     result = PrivacyScore.compute(df, ["age", "zipcode"])

#     assert result == 0.0


# # -----------------------------
# # 6️⃣ Partial Duplication
# # -----------------------------
# def test_privacy_partial_groups():
#     df = pd.DataFrame({
#         "age": [25, 25, 25, 30, 31],
#         "zipcode": [11111, 11111, 11111, 22222, 33333],
#     })

#     result = PrivacyScore.compute(df, ["age", "zipcode"])

#     # Group sizes: 3 (safe), 1, 1 → 2 unique out of 5
#     # score = 1 - (2/5) = 0.6
#     assert result == 0.6