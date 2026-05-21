# Benchmark C++ Engine

Run the built-in benchmark to measure eval throughput and search speed.

## Steps

1. Check that `engines/omble_cavalier++` exists. If it does not, build it first using the `/build` skill.
2. Run the benchmark by piping the UCI command:
   ```
   echo "benchmarking" | engines/omble_cavalier++
   ```
3. Parse the two output lines:
   - `Benchmarking complete: evaluated N positions in X seconds.`
     → compute **eval rate** = N / X (positions per second)
   - `Benchmarking complete: searched to depth 14 in X seconds.`
     → report the **depth-14 search time** in seconds

## Reporting

Present results as a compact table or two-line summary, e.g.:

```
Eval throughput : 12.4M positions/sec  (10,000,000 positions in 0.81s)
Depth-14 search : 4.2s
```

- Express eval rate in **millions/sec** (M/sec) rounded to one decimal.
- If a previous benchmark result appears earlier in the conversation, compute the **percentage change** for each metric and flag whether it is faster (+) or slower (-).
- If the binary is missing or the command fails, say so clearly and offer to run `/build` first.
