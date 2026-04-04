# import numpy as np
# import pytest

# from guardrail_ai.metrics.transparency import SHAPExplainability


# # -----------------------------
# # 1️⃣ Normal SHAP values
# # -----------------------------
# def test_shap_normal():
#     shap_values = np.array([[0.1, -0.2], [0.3, -0.1]])

#     result = SHAPExplainability.compute(shap_values)

#     assert result > 0


# # -----------------------------
# # 2️⃣ Zero SHAP values
# # -----------------------------
# def test_shap_zero_values():
#     shap_values = np.zeros((5, 3))

#     result = SHAPExplainability.compute(shap_values)

#     assert result == 0.0


# # -----------------------------
# # 3️⃣ Large SHAP values
# # -----------------------------
# def test_shap_large_values():
#     shap_values = np.array([[10, -10], [20, -20]])

#     result = SHAPExplainability.compute(shap_values)

#     assert result > 5


# # -----------------------------
# # 4️⃣ Single value
# # -----------------------------
# def test_shap_single_value():
#     shap_values = np.array([5.0])

#     result = SHAPExplainability.compute(shap_values)

#     assert result >= 0


# # -----------------------------
# # 5️⃣ Negative values only
# # -----------------------------
# def test_shap_negative_values():
#     shap_values = np.array([[-1, -2], [-3, -4]])

#     result = SHAPExplainability.compute(shap_values)

#     assert result > 0


# # -----------------------------
# # 6️⃣ Empty input
# # -----------------------------
# def test_shap_empty():
#     shap_values = np.array([])

#     result = SHAPExplainability.compute(shap_values)

#     assert result == 0.0


# # -----------------------------
# # 7️⃣ None input
# # -----------------------------
# def test_shap_none():
#     result = SHAPExplainability.compute(None)

#     assert result == 0.0


# # -----------------------------
# # 8️⃣ Uniform distribution (high entropy)
# # -----------------------------
# def test_shap_uniform_distribution():
#     shap_values = np.array([[1, 1], [1, 1]])

#     result = SHAPExplainability.compute(shap_values)

#     assert result > 0


# # -----------------------------
# # 9️⃣ Concentrated importance (low entropy)
# # -----------------------------
# def test_shap_concentrated_distribution():
#     shap_values = np.array([[10, 0], [10, 0]])

#     result = SHAPExplainability.compute(shap_values)

#     assert result > 0  # still valid but lower spread


# # -----------------------------
# # 🔟 Stability test (repeatability)
# # -----------------------------
# def test_shap_repeatability():
#     shap_values = np.random.rand(10, 5)

#     result1 = SHAPExplainability.compute(shap_values)
#     result2 = SHAPExplainability.compute(shap_values)

#     assert result1 == result2