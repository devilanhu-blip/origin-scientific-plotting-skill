# Preserve a heating and cooling cycle

**Question.** At 320 K the instrument recorded two voltages. Joining them would imply a transition inside one series. The simulated CSV records a change of stage between the two rows.

**Reproduce.** Run the three steps in the [quick start](../../README.md). In the resulting plan inspect the two curves' stage names and inclusive data-row ranges. Follow their points on the PNG.

| Stage | Data rows (header excluded) | Temperatures in acquisition order (K) | Reading at 320 K (mV) |
| --- | --- | --- | --- |
| Heating · 升温 | 1–4 | 290, 300, 310, 320 | 1.81 ± 0.11 |
| Cooling · 降温 | 5–8 | 320, 310, 300, 290 | 1.76 ± 0.09 |

Voltage and half-width come from the same source row. No averaging, sorting, interpolating across stages or model fitting is needed. This example establishes how a two-stage file is represented. Physical hysteresis, equilibrium and significance need experimental evidence beyond this simulation.
