# Notes related to the branch purpose

## Fixing Fallback Oracle Priority Issue After UNNEED→NEED state cycles

When the oracle’s conditional publish service reports the **UNNEED** (offline) state, the `PriceFollower` object keeps counting blocks that have passed since the last publication and price change. Because these counters are not cleared, the next transition back to the **NEED** state lets fallback oracles publish before the chosen oracle. After multiple **UNNEED→NEED** states cycles, this causes the fallback method to publish first, which is incorrect.
