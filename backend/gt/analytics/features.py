"""The ledger as a matrix: per-wallet activity over time and per-wallet behaviour vectors."""
import numpy as np
import pandas as pd

from gt.schema import Transfer

FEATURES = ["n_tx", "mean_gas", "std_gas", "round_frac", "mean_gap_s", "cv_gap", "active_hours"]


def _frame(transfers: list[Transfer]) -> pd.DataFrame:
    return pd.DataFrame([(t.from_addr, t.ts, t.amount, t.gas_price_gwei) for t in transfers],
                        columns=["wallet", "ts", "amount", "gas"])


def activity_matrix(transfers: list[Transfer], bucket_s: int = 3600) -> pd.DataFrame:
    """Rows = sending wallets, columns = time-bucket start (unix s), values = number of txs sent."""
    df = _frame(transfers)
    if df.empty:
        return pd.DataFrame()
    df["bucket"] = df["ts"] // bucket_s * bucket_s
    return df.pivot_table(index="wallet", columns="bucket", values="ts", aggfunc="count", fill_value=0)


def _row(g: pd.DataFrame) -> dict:
    gaps = np.diff(np.sort(g["ts"].to_numpy()))
    enough = len(g) >= 3
    mean_gap = gaps.mean() if enough else np.nan
    return {
        "n_tx": len(g),
        "mean_gas": g["gas"].mean(),
        "std_gas": g["gas"].std(ddof=0),
        "round_frac": float(np.isclose(g["amount"] * 10, np.round(g["amount"] * 10)).mean()),
        "mean_gap_s": mean_gap,
        "cv_gap": gaps.std() / mean_gap if enough and mean_gap else np.nan,
        "active_hours": g["ts"].floordiv(3600).mod(24).nunique(),
    }


def wallet_features(transfers: list[Transfer]) -> pd.DataFrame:
    """One behaviour vector per sending wallet. Fewer than 3 sent txs → gap stats are NaN."""
    df = _frame(transfers)
    if df.empty:
        return pd.DataFrame(columns=FEATURES)
    return pd.DataFrame({w: _row(g) for w, g in df.groupby("wallet")}).T[FEATURES]
