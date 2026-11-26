# Validation record

| Evidence | Result and scope |
| --- | --- |
| Public source candidate `v0.1.0-alpha.1` | Offline CSV inspection, plans, style history and PNG previews. The development-host configuration is recorded in [Dependencies](dependencies.md). |
| Current candidate, Origin creation/export | **NOT_EXECUTED**. This distribution provides offline previews and omits the private native worker. |
| Historical production Pilot, 2026-11-25 | **PASS_LIMITED_NATIVE_P3_MANAGED_PILOT** for the named private RC3 version on one host with one fixed SIMULATED task. |
| Real/de-identified data and an independent first-time user | **REAL_DATA_INPUT_PENDING** and **EXTERNAL_TRIAL_PENDING**. |

The results below describe the local rehearsal and the historical private pilot. GitHub records hosted Windows CI against the exact commit on the [workflow runs page](https://github.com/devilanhu-blip/origin-scientific-plotting-skill/actions/workflows/offline.yml).

### Current offline checks

Six command-line regression cases passed on the Windows development host. They exercised source row order, numerical values and half-widths, preset changes with the same scientific inputs, rejection of ambiguous errors and unsupported bindings, saving and pinning two editions of a style, and digest checks when a source or draft changes. The published example can be rerun using the [test instructions](../CONTRIBUTING.md).

The three [gallery PNGs](styles.md) were opened and reviewed. Each shows the same simulated heating/cooling series, source units, legend, half-width definition and preview label. PNG structure checks found only image header, image data and end chunks. The [gallery snapshots](gallery/snapshots.json) retain the example's source digest, plans and style choices.

### Public installation rehearsal

A release ZIP was expanded into a new Windows directory containing spaces and Chinese characters on a different drive from the development project. A separately selected CPython and a new virtual environment installed the hashed Windows wheel from a local wheelhouse. The documented PowerShell steps produced a PNG showing both stages, both 320 K readings, axis units and the stated simulated uncertainty. The clean environment had no Origin Python bindings or private helpers. A second instrumented call successfully rendered a draft while rejecting access to the development/data volumes, external processes, native imports and network connections.

The same host ran the CI commands using the independently downloaded Noto fonts. Both the default-font and CI-font variants passed the six offline test groups. Both first-run images were viewed. This rehearsal did not observe a physically separate workstation or a GitHub-hosted job.

For the identical simulated request, clean and monochrome tasks were also compiled through an untouched personal-package copy and through the Alpha entry. For each preset the task bytes, complete plan, effective styles and appearance snapshots matched. The PNGs differed only in the offline provenance label. This comparison covers those two example runs.

### What the historical Pilot established

Private version `M4-MVP1-0.6.0-personal-p3-rc3` ran one new Origin session. The graph contained two temperature-sweep series from a UTF-8 CSV, each with same-unit symmetric absolute Y half-widths. The declared mode was `SKILL_MANAGED_SERIES_VISIBILITY`. It addressed each series and its associated error object. `NATIVE_PARENT_AUTO_FOLLOW=NOT_EVALUATED`.

- **Science and editability.** The saved OPJU was reopened. The review checked 8 centers, 8 half-widths and 16 endpoints against an independent decimal calculation at initial reopen, edited-copy reopen and original restoration. Changing the first value from 1.12 ± 0.06 mV to 0 ± 0 mV and changing the X-axis title persisted in the copy. Restoring the original recovered its original data, title and file digest. The edited point fell outside the displayed Y range and was confirmed by data readback.
- **Visibility.** Five images per stage recorded both series visible, first hidden, first restored, second hidden and second restored. Reviewers viewed all ten native PNGs. At 310 K, the distinct 1.41 mV lower cap and 1.60 mV upper cap identified each series. Both restored states matched their stage's initial decoded pixels. Ten redraw calls returned an unconfirmed result. Acceptance used actual readback and image inspection.
- **Final exports.** Reviewers inspected the 2400 × 1701 PNG and the full rendered page of the final PDF. The PDF had five Type 3 glyph resources. Chinese label extraction failed for the checked labels, and changing PDF text in an editor was untested. OPJU edit persistence is the editability evidence.
- **Machine and review outcomes.** The machine recorded `NATIVE_MACHINE_PASS_VISUAL_PENDING`. The subsequent visual and scientific review supports the limited result above. The archived machine result and earlier failures retain their original status.

### Traceability across versions

The historical RC3 candidate ZIP had SHA-256 `879b528d1a2229d14dc3a44cfa6edaef213fd27e083f07bcf63ed86b7a799469`. The later personal trial ZIP had SHA-256 `a28addc17294a4de88957f214be806d40abcf6494847e14872a548dba1558340`. Verification of that personal package covered all 53 payload entries. Its 37 production Python files and four runtime resources matched the approved RC3 and staged Pilot sources. The subsequent natural-language trial produced an offline SIMULATED preview. The public Alpha changes the runtime entry, environment handling and packaging. It has a separate identity.

This is a newly written public summary of private evidence. The gallery is labeled **OFFLINE_PREVIEW**. Historical **ORIGIN_NATIVE_EXPORT** files, OPJU projects, machine logs, local identities and approval records stay in private storage. A later native compatibility claim requires a named trial on its actual release code and host, with permission for the specific real/de-identified input, source/half-width checks, saved-edit reopen and visual review of both exports.

### Historical gates

| Gate | Recorded state |
| --- | --- |
| `application_audit` | `REVIEW` |
| `delivery` | `LOCKED` |
| `D4` | `FAIL` |
| `D5` | `HOLD` |
| `P5` | `NOT_STARTED` |
| `V0.3` | `NOT_DEPLOYED` |
