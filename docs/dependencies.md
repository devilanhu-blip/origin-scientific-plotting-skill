# Dependencies and tested environments

You can inspect a CSV, choose a style and generate a PNG with Origin absent. Once Python, Pillow and suitable fonts are available locally, the plotting commands work offline. The first installation of Python or Pillow and provisioning the CI runner can require a download.

| Component | Public Alpha support | Environment checked |
| --- | --- | --- |
| Operating system | Windows x86-64, ordinary local disk paths | Windows 11 x64, build 26300 |
| Interpreter | CPython 3.12.x x64, selected by the caller | CPython 3.12.15 x64 on the development machine. Other patch releases and Windows builds have no independent trial on record. |
| PNG renderer | Pillow 12.3.0, CPython 3.12 Windows x86-64 wheel | Official wheel SHA-256 `a2b55dd6b2a4c4b7d87ffa56bdb33fdc5fdb9a462173861a7bc097f17d91cb09` |
| Labels | Local regular and bold font files covering the characters in the figure | Microsoft YaHei regular/bold on the development machine. Hosted CI is configured to use Noto Sans CJK SC 2.004. |
| Origin application and Python automation bindings | Outside this package's supported runtime | Separate historical RC3 Pilot on 64-bit Origin 2026b, API `@V = 10.350243`, with `originpro 1.1.15` and `OriginExt 1.2.5`. Current Alpha native status is **NOT_EXECUTED**. |

### Obtaining the runtime

1. Use a 64-bit CPython 3.12 installation from a trusted distributor. The Python 3.12.15 security release provides source. Python 3.12.10 was the last 3.12 release with python.org Windows installers. The recorded 3.12.15 test identifies a patch level, not a Windows installer available from that release page. [Python 3.12.15 release](https://www.python.org/downloads/release/python-31215/) · [Python 3.12.10 release](https://www.python.org/downloads/release/python-31210/)
2. Follow the [installation instructions](../README.md) in a project-local environment. The dependency lock identifies the Pillow version and wheel hash. For a disconnected computer, obtain the named wheel from the official release on another computer and transfer it in accordance with local policy. The `cp312-cp312-win_amd64` tags select the required Python ABI and platform. [Pillow 12.3.0 release files](https://pypi.org/project/pillow/12.3.0/#files)
3. The default Chinese labels use `msyh.ttc` and `msyhbd.ttc` from Windows Fonts. Alternatively, select regular and bold fonts with Chinese coverage using the local configuration fields `font_regular` and `font_bold`. An openly licensed pair is the SC Regular and Bold OTF from the Noto Sans CJK 2.004 release. Run `doctor` using the same interpreter and config as the draft. Verify the glyphs in the resulting PNG for your own labels. [Microsoft YaHei](https://learn.microsoft.com/en-us/typography/font-list/microsoft-yahei) · [Noto Sans CJK 2.004](https://github.com/notofonts/noto-cjk/releases/tag/Sans2.004)

### Historical native dependencies

The prior Pilot used a licensed local Origin installation, its COM server and two private host scripts, `origin_tools.py` and `doctor.py`. Those scripts have no established public distribution route. The Alpha's offline implementation needs neither script. An OriginLab desktop license and the Python packages are separately obtained products. Installing the packages alone cannot reproduce the private Pilot. [OriginLab download and licensing](https://www.originlab.com/demodownload.aspx) · [originpro 1.1.15](https://pypi.org/project/originpro/1.1.15/) · [OriginExt 1.2.5](https://pypi.org/project/originext/1.2.5/)

See the [historical verification scope](validation.md) for the tested operations and the [third-party notices](../THIRD_PARTY_NOTICES.md) for component terms.
