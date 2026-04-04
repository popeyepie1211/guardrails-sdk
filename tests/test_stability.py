# import numpy as np
# import pytest

# from guardrail_ai.metrics.stability import PSI


# # -----------------------------
# # 1️⃣ Identical Distributions → PSI = 0
# # -----------------------------
# def test_psi_no_drift():
#     expected = np.array([1, 2, 3, 4, 5])
#     actual = np.array([1, 2, 3, 4, 5])

#     result = PSI.compute(expected, actual)

#     assert pytest.approx(result, 0.0001) == 0.0




# # -----------------------------
# # 3️⃣ Significant Drift
# # -----------------------------
# def test_psi_large_drift():
#     expected = np.array([1, 1, 1, 1, 1])
#     actual = np.array([10, 10, 10, 10, 10])

#     result = PSI.compute(expected, actual)

#     assert result > 0.25


# # -----------------------------
# # 4️⃣ Different Distribution Shapes
# # -----------------------------
# def test_psi_different_distribution():
#     expected = np.array([1, 2, 3, 4, 5])
#     actual = np.array([5, 5, 5, 5, 5])

#     result = PSI.compute(expected, actual)

#     assert result > 0


# # -----------------------------
# # 5️⃣ Empty Input
# # -----------------------------
# def test_psi_empty():
#     expected = np.array([])
#     actual = np.array([])

#     result = PSI.compute(expected, actual)

#     assert result == 0.0


# # -----------------------------
# # 6️⃣ Zero Handling (edge case)
# # -----------------------------
# def test_psi_zero_handling():
#     expected = np.array([0, 0, 0, 0, 1])
#     actual = np.array([0, 0, 0, 1, 1])

#     result = PSI.compute(expected, actual)

#     assert result >= 0 and result < 0.25


# # -----------------------------
# # 7️⃣ Large Input Stability
# # -----------------------------
# def test_psi_large_input():
#     expected = np.random.normal(0, 1, 1000)
#     actual = np.random.normal(0, 1, 1000)

#     result = PSI.compute(expected, actual)

#     assert result >= 0 and result < 0.1

# def test_psi_moderate_vs_large():
#     np.random.seed(42)

#     expected = np.random.normal(0, 1, 1000)
#     moderate = np.random.normal(0.5, 1, 1000)
#     large = np.random.normal(1.5, 1, 1000)

#     psi_mod = PSI.compute(expected, moderate)
#     psi_large = PSI.compute(expected, large)

#     assert psi_mod < psi_large

# def test_psi_basic_behavior():
#     expected = np.array([1, 2, 3])
#     actual = np.array([4, 5, 6])

#     result = PSI.compute(expected, actual)

#     assert result > 0
    
    
# def test_psi_asymmetry():
#     expected = np.array([1, 2, 3, 4, 5])
#     actual = np.array([10, 10, 10, 10, 10])

#     psi1 = PSI.compute(expected, actual)
#     psi2 = PSI.compute(actual, expected)

#     assert psi1 != psi2
    
# def test_psi_bin_sensitivity():
#     expected = np.random.normal(0, 1, 1000)
#     actual = np.random.normal(0, 1, 1000)

#     psi_5 = PSI.compute(expected, actual, bins=5)
#     psi_20 = PSI.compute(expected, actual, bins=20)

#     assert psi_5 >= 0
#     assert psi_20 >= 0

# def test_psi_constant_equal():
#     expected = np.array([5, 5, 5, 5])
#     actual = np.array([5, 5, 5, 5])

#     result = PSI.compute(expected, actual)

#     assert result == 0.0