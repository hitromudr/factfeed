"""
Temperature scaling for confidence calibration.

DeBERTa zero-shot models tend to produce overconfident scores. Temperature
scaling divides the logit by a learned temperature parameter before applying
the sigmoid, pulling extreme probabilities toward 0.5.

Default temperature=1.0 means no scaling (passthrough).
"""

import numpy as np


class TemperatureScaler:
    """Calibrate raw confidence scores using temperature scaling."""

    def __init__(self, temperature: float = 1.0):
        self.temperature = temperature

    def calibrate(self, raw_score: float) -> float:
        """Apply temperature scaling to a raw confidence score.

        Returns the calibrated score in (0, 1).
        """
        if self.temperature == 1.0:
            return raw_score
        return self._calibrate_with_T(raw_score, self.temperature)

    def fit(self, raw_scores: list[float], true_labels: list[int]) -> float:
        """Find the optimal temperature on a calibration set.

        Args:
            raw_scores: Raw confidence scores from the classifier.
            true_labels: Binary labels (1 = correct class, 0 = incorrect).

        Returns:
            The fitted temperature value.
        """
        from scipy.optimize import minimize_scalar
        from sklearn.metrics import log_loss

        def nll(T):
            cal = [self._calibrate_with_T(s, T) for s in raw_scores]
            probs = [[1 - p, p] for p in cal]
            return log_loss(true_labels, probs)

        result = minimize_scalar(nll, bounds=(0.1, 10.0), method="bounded")
        self.temperature = result.x
        return self.temperature

    def _calibrate_with_T(self, raw_score: float, T: float) -> float:
        """Apply temperature scaling with explicit temperature value."""
        logit = np.log(raw_score / (1 - raw_score + 1e-8))
        scaled = logit / T
        return float(1 / (1 + np.exp(-scaled)))
