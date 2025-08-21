# Oracle Turn Fallback Logic Improvements

This document describes the improvements made to the oracle turn and fallback logic to enhance debugging, synchronization validation, and robustness.

## Overview

The oracle system uses a fallback mechanism where if the primary oracle doesn't publish within a certain time, fallback oracles are enabled in a progressive sequence. This ensures system reliability even if some oracles are offline or experiencing issues.

## Key Components

### 1. Oracle Order Calculation (L2)

The oracle order is calculated deterministically using:
- Block hash of the last published price
- Stakes of all selected oracles
- A randomization algorithm that ensures fairness

### 2. Fallback Sequence

The fallback sequence determines how many oracles are enabled as blocks pass:
- Block 0: Only primary oracle enabled
- Block 1: Primary + first N fallbacks enabled
- Block 2: Primary + first M fallbacks enabled
- And so on...

The sequence is configured via `entering_fallbacks_amounts` parameter.

## Improvements Made

### Enhanced Logging

#### Oracle Order Logging
```
ORACLE_ORDER_L2: block_hash=0x1234567890... selected_count=12 calculated_order=[oracle1, oracle2, ...] primary_oracle=oracle1
```

#### Configuration Validation Logging  
```
CONFIG_VALIDATION: entering_fallbacks_amounts=[2, 4, 6, 8, 10] price_publish_blocks=1 price_delta_pct=0.05 trigger_valid_publication_blocks=30 fallback_sequence=[1, 3, 5, 7, 9, 11, 12]
```

#### Fallback State Logging
```
FALLBACK_STATE_CHECK: oracle=oracle2 blocks_since_allowed=1 oracle_order=[oracle1, oracle2, oracle3, oracle4, oracle5] sequence=[1, 3, 5, 7, 9, 11, 12] only_chosen=False
FALLBACK_CALCULATION: blocks_since_allowed=1 sequence_index=1 fallbacks_enabled_count=3 enabled_fallbacks=[oracle2, oracle3] oracle_is_enabled_fallback=True index_condition_met=True
```

### New Methods

#### `get_fallback_debug_info(vi, oracle_addresses)`
Returns comprehensive debug information about the current fallback state:
```python
{
    'block_hash': '0x1234...',
    'oracle_order_L2': ['oracle1', 'oracle2', ...],
    'primary_oracle': 'oracle1', 
    'fallback_sequence': [1, 3, 5, 7, 9, 11, 12],
    'config': { ... },
    'selected_oracles_count': 12,
    'fallback_scenarios': [
        {
            'blocks_since_allowed': 0,
            'num_oracles_enabled': 1,
            'enabled_oracles': ['oracle1']
        },
        ...
    ]
}
```

#### `validate_configuration_consistency(expected_config=None)`
Validates configuration parameters and optionally compares against expected values:
```python
{
    'valid': True,
    'warnings': [],
    'errors': [],
    'config_values': { ... }
}
```

### Bug Fixes

- Fixed potential off-by-one error in fallback sequence calculation that could prevent all oracles from being enabled
- Improved boundary condition handling in sequence generation

## Debugging Synchronization Issues

### Step-by-step Process

1. **Enable Enhanced Logging**: Set logging level to INFO on all oracle nodes

2. **Compare Configuration**: Look for `CONFIG_VALIDATION` logs across nodes:
   ```bash
   grep "CONFIG_VALIDATION" oracle1.log
   grep "CONFIG_VALIDATION" oracle2.log  
   # Compare output
   ```

3. **Verify Oracle Ordering**: Check `ORACLE_ORDER_L2` logs:
   ```bash
   grep "ORACLE_ORDER_L2" oracle1.log
   grep "ORACLE_ORDER_L2" oracle2.log
   # Should show identical oracle orders for same block hash
   ```

4. **Analyze Fallback Calculations**: Examine `FALLBACK_CALCULATION` logs:
   ```bash
   grep "FALLBACK_CALCULATION" oracle1.log | head -10
   ```

5. **Use Debug Info Method**: Call `get_fallback_debug_info()` on suspect oracles and compare output

### Common Issues

1. **Configuration Mismatch**: Different `entering_fallbacks_amounts` across oracles
2. **Block Hash Differences**: Oracles using different last publication blocks
3. **Oracle List Inconsistency**: Different selected oracle lists
4. **Timing Desynchronization**: Oracles at different block heights

## Configuration Guidelines

### Recommended Settings

```python
# Standard production configuration
ORACLE_ENTERING_FALLBACKS_AMOUNTS = b'\x02\x04\x06\x08\n'  # [2,4,6,8,10]
ORACLE_PRICE_PUBLISH_BLOCKS = 1
ORACLE_PRICE_DELTA_PCT = 0.05
ORACLE_TRIGGER_VALID_PUBLICATION_BLOCKS = 30
```

### Configuration Validation

Ensure:
- `trigger_valid_publication_blocks > len(entering_fallbacks_amounts)`
- `price_publish_blocks >= 0`
- `price_delta_pct > 0`

## Examples

### Fallback Sequence with 12 Oracles

Configuration: `[2, 4, 6, 8, 10]`

| Blocks Since | Oracles Enabled | Oracle Indices |
|--------------|-----------------|----------------|
| 0            | 1               | [0]            |
| 1            | 3               | [0, 1, 2]      |
| 2            | 5               | [0, 1, 2, 3, 4] |
| 3            | 7               | [0, 1, 2, 3, 4, 5, 6] |
| 4            | 9               | [0, 1, 2, 3, 4, 5, 6, 7, 8] |
| 5            | 11              | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] |
| 6+           | 12              | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] |

## Testing

The improvements include comprehensive tests that verify:
- Fallback sequence calculation correctness
- Enhanced logging functionality  
- Configuration validation
- Debug information generation

Run tests with:
```bash
python test_oracle_turn_improvements.py
```

Use debug helper:
```bash
python oracle_debug_helper.py --sequence --oracles 12
```

## Backward Compatibility

All changes are backward compatible:
- Existing log parsing scripts will continue to work
- Core fallback logic behavior is unchanged
- Configuration parameters remain the same
- Method signatures are preserved