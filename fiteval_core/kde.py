"""Bounded-support kernel CDF replicating MATLAB ksdensity.

fitevaluation (L3486) calls
    ksdensity(dist, xi, 'function','cdf', 'support',[lowerb 1.001])
MATLAB maps the data to an unbounded scale with the logit-type transform
z = log((x-L)/(U-x)), selects the normal-optimal bandwidth from a robust
(MAD-based) sigma of the transformed data, and evaluates the kernel CDF
there; the CDF is invariant under the monotone transform, so
F(x) = mean_i Phi((z(x)-z_i)/h).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


class KDEError(ValueError):
    """Raised when the CDF cannot be built (mirrors MATLAB ksdensity error)."""


def ksdensity_cdf(dist: np.ndarray, xi: np.ndarray,
                  support: tuple[float, float]) -> np.ndarray:
    """Kernel CDF of `dist` evaluated at `xi` on bounded `support`."""
    dist = np.asarray(dist, dtype=float).ravel()
    dist = dist[~np.isnan(dist)]
    xi = np.asarray(xi, dtype=float)
    lo, hi = support
    if dist.size == 0:
        raise KDEError("No data to build the distribution")
    if np.any(dist <= lo) or np.any(dist >= hi):
        raise KDEError("Data must lie inside the support interval")

    z = np.log((dist - lo) / (hi - dist))
    med = np.median(z)
    sig = np.median(np.abs(z - med)) / 0.6745
    if sig <= 0:
        sig = z.max() - z.min()
    if sig > 0:
        h = sig * (4.0 / (3.0 * dist.size)) ** 0.2
    else:
        h = 1.0
    if not np.isfinite(h) or h == 0:
        raise KDEError("Cannot compute a kernel bandwidth "
                       "(all values are identical)")

    fi = np.empty(xi.shape, dtype=float)
    inside = (xi > lo) & (xi < hi)
    fi[xi <= lo] = 0.0
    fi[xi >= hi] = 1.0
    if np.any(inside):
        zq = np.log((xi[inside] - lo) / (hi - xi[inside]))
        # mean over data kernels; broadcast (n_q, 1) - (n_data,)
        fi[inside] = norm.cdf((zq[:, None] - z[None, :]) / h).mean(axis=1)
    return fi
