# Capability matrix

| Status | Scope | Evidence or boundary |
| --- | --- | --- |
| Offline plotting | Inspect one UTF-8 CSV, map the quantities, units, series or stages and explicit pointwise symmetric absolute Y half-widths. Preserve acquisition order and repeated X values. Create a traceable plan and a static PNG with two series. | [Reproducible example](../README.md) and [simulated gallery](styles.md). |
| Pairing in the offline plan | `--visibility managed` records which error bars belong to each curve. The static PNG shows both pairs. | Interactive show/hide and Origin visibility automation are unavailable in this distribution. |
| Offline styles | Choose a clean, monochrome or presentation profile. Change plot appearance and legend placement. Save and pin revisions of local styles. | [Style examples](styles.md). |
| Outside this distribution | Origin automation, creation or editing of OPJU files, and Origin-native exports. Excel import, complex fits, 3D and multi-panel figures are also outside the Alpha's scope. | The package contains no Origin execution connector. Earlier native results apply only to the separate version and host on which they were obtained. [Validation scope](validation.md) |
| Pending trials | Independent first-time installation and an authorized trial with real or de-identified data. | [Trial cards](trials.md) |

The supported environment is Windows x64 with CPython 3.12 x64. Any future Origin connector needs its own rights review and validation against the intended release and runtime. [Dependencies](dependencies.md)
