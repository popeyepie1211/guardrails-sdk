# import numpy as np
# import pytest

# from guardrail_ai.metrics.security import Security


# # -----------------------------
# # 1️⃣ No Change → L∞ = 0
# # -----------------------------
# def test_linf_no_change():
#     expected = np.array([1, 2, 3])
#     actual = np.array([1, 2, 3])

#     result = Security.linf_norm(expected, actual)

#     assert result == 0.0


# # -----------------------------
# # 2️⃣ Small Change
# # -----------------------------
# def test_linf_small_change():
#     expected = np.array([1, 2, 3])
#     actual = np.array([1, 2, 4])

#     result = Security.linf_norm(expected, actual)

#     assert result == 1.0


# # -----------------------------
# # 3️⃣ Large Adversarial Change
# # -----------------------------
# def test_linf_large_change():
#     expected = np.array([1, 1, 1])
#     actual = np.array([10, 10, 10])

#     result = Security.linf_norm(expected, actual)

#     assert result > 5


# # -----------------------------
# # 4️⃣ OOD No Drift
# # -----------------------------
# def test_ood_no_drift():
#     np.random.seed(42)

#     expected = np.random.normal(0, 1, 1000)
#     actual = np.random.normal(0, 1, 1000)

#     result = Security.ood_score(expected, actual)

#     assert result < 0.05


# # -----------------------------
# # 5️⃣ OOD Moderate Drift
# # -----------------------------
# def test_ood_moderate():
#     np.random.seed(42)

#     expected = np.random.normal(0, 1, 1000)
#     actual = np.random.normal(3, 1, 1000)

#     result = Security.ood_score(expected, actual)

#     assert result > 0.1


# # -----------------------------
# # 6️⃣ OOD Extreme Drift
# # -----------------------------
# def test_ood_extreme():
#     expected = np.random.normal(0, 1, 1000)
#     actual = np.random.normal(10, 1, 1000)

#     result = Security.ood_score(expected, actual)

#     assert result > 0.5


# # -----------------------------
# # 7️⃣ Empty Input
# # -----------------------------
# def test_security_empty():
#     expected = np.array([])
#     actual = np.array([])

#     result = Security.compute(expected, actual)

#     assert result["linf"] == 0.0
#     assert result["ood_score"] == 0.0


# # -----------------------------
# # 8️⃣ Combined Metric
# # -----------------------------
# def test_security_combined():
#     expected = np.array([1, 2, 3])
#     actual = np.array([2, 3, 10])

#     result = Security.compute(expected, actual)

#     assert "linf" in result
#     assert "ood_score" in result