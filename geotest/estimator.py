"""The pre-registered estimator for the 2026 market test, shared by design and readout.

Two arms cross the 20 markets (a 2x2 factorial): each arm's markets are compared
with the other markets, so each arm is measured on all 20.

* For arm k with markets T_k, the contrast is a ratio difference-in-differences on
  won deals summed over the measurement window:
      c_k = W(T_k) - r_k * W(not T_k),   r_k = P(T_k) / P(not T_k)
  where W is deals in the window and P is deals in the PRE_WEEKS before the test.
* The other arm also moves deals on both sides of the contrast. With each market's
  effect proportional to its planned dose (the dollars the plan adds or removes),
  E[c] = A theta, A[k, j] = D_j(T_k) - r_k D_j(not T_k). Solving the 2x2 system
  removes the cross-arm term, and arm k's lift is theta_k times its total dose.
* Intervals and power come from placebo windows: the same estimator applied to
  2023 to 2025 windows where nothing was tested.
"""

from __future__ import annotations

import numpy as np

Z_90 = 1.6448536269514722    # one-sided 5%: the 90% interval's edge
Z_80 = 0.8416212335729143    # 80% power
MDE_Z = Z_90 + Z_80          # 2.487


def contrasts(pre: np.ndarray, win: np.ndarray, arms: np.ndarray) -> np.ndarray:
    """pre, win: (..., G) deal sums; arms: (K, G) bool. Returns (..., K)."""
    out = []
    for t in arms:
        r = pre[..., t].sum(-1) / pre[..., ~t].sum(-1)
        out.append(win[..., t].sum(-1) - r * win[..., ~t].sum(-1))
    return np.stack(out, axis=-1)


def dose_matrix(pre: np.ndarray, arms: np.ndarray, doses: np.ndarray) -> np.ndarray:
    """A[k, j] = D_j(T_k) - r_k D_j(not T_k), from pre-period deals (G,)."""
    K = arms.shape[0]
    A = np.zeros((K, K))
    for k, t in enumerate(arms):
        r = pre[t].sum() / pre[~t].sum()
        for j in range(K):
            A[k, j] = doses[j, t].sum() - r * doses[j, ~t].sum()
    return A


def lifts(pre: np.ndarray, win: np.ndarray, arms: np.ndarray, doses: np.ndarray) -> np.ndarray:
    """Each arm's lift in deals over the window, cross-arm effects removed. (..., K)."""
    c = contrasts(pre, win, arms)
    if pre.ndim == 1:
        A = dose_matrix(pre, arms, doses)
        theta = np.linalg.solve(A, c)
        return theta * doses.sum(axis=1)
    out = np.zeros_like(c)
    for i in range(c.shape[0]):
        A = dose_matrix(pre[i], arms, doses)
        out[i] = np.linalg.solve(A, c[i]) * doses.sum(axis=1)
    return out


def window_sums(deals: np.ndarray, start: int, n_pre: int, n_win: int) -> tuple[np.ndarray, np.ndarray]:
    """deals (T, G) -> pre-period and window sums (G,) for a test starting at `start`."""
    return deals[start - n_pre:start].sum(0), deals[start:start + n_win].sum(0)


def placebo(deals: np.ndarray, arms: np.ndarray, doses: np.ndarray, starts, n_pre: int, n_win: int) -> np.ndarray:
    """The estimator on windows where nothing was tested. (len(starts), K)."""
    cum = np.vstack([np.zeros((1, deals.shape[1])), np.cumsum(deals, 0)])
    s = np.asarray(starts)
    pre = cum[s] - cum[s - n_pre]
    win = cum[s + n_win] - cum[s]
    return lifts(pre, win, arms, doses)


def count_noise_floor(deals: np.ndarray, arms: np.ndarray, n_win: int) -> np.ndarray:
    """Smallest possible error sd per arm: Poisson noise in both sides' window deals,
    at the last 52 weeks' rate."""
    rate = deals[-52:].sum(0) / 52 * n_win
    out = []
    for t in arms:
        r = rate[t].sum() / rate[~t].sum()
        out.append(np.sqrt(rate[t].sum() + r * r * rate[~t].sum()))
    return np.array(out)
