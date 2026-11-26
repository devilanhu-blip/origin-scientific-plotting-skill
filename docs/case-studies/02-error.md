# Bind an error bar to its own measurements

**Question.** The two points at 310 K have different Y values and different uncertainty intervals. Can the exact endpoints be recovered from the file?

**Reproduce.** Open the [simulated CSV](../../.agents/skills/origin-alpha/examples/SIMULATED_voltage.csv) as UTF-8. At data row 3 the reading is 1.46 mV and the half-width is 0.05 mV. The bar runs from 1.41 to 1.51 mV. At row 6 the reading is 1.53 mV with a 0.07 mV half-width, so the endpoints are 1.46 and 1.60 mV. Compare with the [clean preview](../gallery/SIMULATED-clean-offline-preview.png). The CLI requires an explicit source, error definition and compatible unit.

Run the offline tests in [Contributing](../../CONTRIBUTING.md) for negative examples from earlier failures. A bare SD, SEM or unknown uncertainty does not specify the half-width used here. The static preview records one main curve/error pair per stage. Visibility toggling in a live graph belongs to a separate native validation.
