# Third-party notices

The project source and tests, presets, documentation, bundled simulated CSV and original gallery PNGs are covered by the MIT License, copyright (c) 2026 Monys Qi. Third-party software and font files are obtained separately under their own terms. [MIT License](LICENSE) · [Licensing scope](docs/licensing.md)

| Component | Use in the offline Alpha | Source and applicable terms |
| --- | --- | --- |
| CPython and standard library | User-provided interpreter. Python's release includes its own notices for incorporated components. | [Python 3.12 license and notices](https://docs.python.org/3.12/license.html) |
| Pillow 12.3.0 | Separately installed PNG renderer. Pillow identifies MIT-CMU for its source. Each binary distribution carries license material for its incorporated libraries. | [Pillow 12.3.0 license](https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE) · [release files](https://pypi.org/project/pillow/12.3.0/#files) |
| Microsoft YaHei regular and bold | Optional Windows-supplied typefaces used for localized PNG labels. A PNG stores rendered pixels. Font software remains on the user's computer under its applicable terms. | [Family and availability](https://learn.microsoft.com/en-us/typography/font-list/microsoft-yahei) · [Microsoft font use and redistribution FAQ](https://learn.microsoft.com/en-us/typography/fonts/font-faq) |
| Noto Sans CJK SC 2.004 | Alternative regular/bold font pair for previews. CI retrieves the fonts to its temporary area. The font files carry the SIL Open Font License 1.1. | [Upstream release](https://github.com/notofonts/noto-cjk/releases/tag/Sans2.004) · [license at that tag](https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/LICENSE) |
| GitHub Actions checkout and setup-python | Hosted test workflow references the upstream actions. Their implementation is downloaded by the runner. | [checkout license](https://github.com/actions/checkout/blob/v4.2.2/LICENSE) · [setup-python license](https://github.com/actions/setup-python/blob/v5.6.0/LICENSE) |

## OriginLab software

Origin and OriginPro are OriginLab products. This Alpha runs without Origin software, its automation bindings or private host helpers. Rights to any private helpers would need separate review if a future connector used them. [OriginLab](https://www.originlab.com/demodownload.aspx) · [Dependency scope](docs/dependencies.md)
