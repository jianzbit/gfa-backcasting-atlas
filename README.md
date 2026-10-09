# GFA Backcasting Atlas — Indicator 1.1

An English, portable interactive presentation of the frozen 9 October 2026 research snapshot. It contains fourteen core model variants (v0.1–v0.13, with Compact and Expanded v0.9), the 43-factor library, 195-country historical estimates, matched excluded-country diagnostics, Korean transfer diagnostics and refitted group ablations. Earlier audits and the fixed 0.50 trend candidate remain linked as precursor studies.

## Evidence and interpretation

- The primary comparison contains ten structures refitted under the same six-country weak-native protocol. Each held country is excluded from its fit. The website never calculates validation from an in-sample trajectory.
- Original release trajectories and matched-six global comparator trajectories are distinct selectable snapshots. Neither is held-out validation.
- v0.1, v0.2, v0.4 and v0.6 do not have scores under the latest matched-six protocol. The available original seven-country diagnostics are shown separately, with Finland's unresolved register bridge and original date rules retained.
- Errors are country-macro mean absolute log deviations ×100 on ratios relative to 2020. They are not exact percentage errors, global accuracy or evidence that the 2020 inherited anchors are correct.
- v0.13 provides 193 complete paths (188 shared paths and five fallbacks). PSE stays missing; VAT retains only 2020. Missing values are never replaced with zeros.
- Six eligible native residential/register references are not independent, globally representative all-use GFA truth. Korea's partial external diagnostic was already exposed during development. No calibrated GFA confidence intervals or validated Area of Applicability are available.
- v0.3 remains the research default. No release is promoted by this website.

## Rebuild and serve

From the original research repository root:

```sh
python3 scripts/build_research_site.py
python3 -m http.server 8788 --bind 127.0.0.1 --directory research-site
```

Open `http://127.0.0.1:8788/`. The build reads frozen source files, checks preserved anchors, missingness and matched metrics, and exports static data. It never refits a model. The website uses local HTML/CSS/JavaScript and native SVG charts; there is no package installation, remote font, CDN, analytics, login, database or client-side model training.

`downloads/source-manifest.json` records the source-file checksums and pinned research commit. `downloads/export-verification.json` records export checks. Country downloads contain original units of m²; chart and table units are explicit.

## Publication boundary

The presentation directory can be deployed at the root of a dedicated GitHub Pages repository. It contains selected research results and source metadata, not the private research repository history, raw data lake, credentials or Forge session records. Original implementation and archive links require access to the original team repository. Its scientific models remain reproducible from that pinned source archive.

Publication to a public repository makes these selected research results publicly readable. The original research repository must remain private. GitHub Pages can publish this buildless directory from the `main` branch root using the included `.nojekyll` marker; all browser asset links are relative and work at a project subpath.

External source documentation is credited within the factor library. This research presentation is not an official IEA, UNEP, GlobalABC, national-statistics or satellite-product release. Institutional adoption and website publication do not establish empirical accuracy.
