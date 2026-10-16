# Global Floorspace Atlas

English interactive presentation of the frozen Indicator 1.1 v16 research estimates, updated 16 October 2026.

The homepage covers 195 country series from 2015 to 2030. Users can select Total, Residential or Non-residential GFA and any valid start/end years. The calculator reports endpoint floorspace, net area change, cumulative growth and compound annual growth. Charts show levels, annual changes, annual growth rates or a 2020-normalized index. Country CSV and standalone SVG downloads retain explicit units and estimate roles.

The primary global aggregate contains the same 194 countries at every date. State of Palestine is a separately labeled source-conditioned supplement. Its 2023–2030 values are a counterfactual unadjusted stock baseline without measured conflict destruction/reconstruction; they are excluded from the primary global total.

## Contents

- `index.html`, `explorer.css`, `explorer.js`: current country explorer, methods, factors and evidence.
- `data/explorer-data.js`: full-precision central values, supplied sensitivity envelopes and actual country factor roles.
- `downloads/v16-*`: unchanged research CSV/specification/source exports and provenance.
- `comparison/`: cross-dataset disagreement tables and interactive report, including native physical quantities and explicitly conditional area equivalents.
- `history.html`: preserved 9 October 2026 atlas of fourteen early model variants. Its archived data, scores and assets retain their earlier scope.
- `history-README.md`: documentation for that earlier snapshot.

The website uses local HTML, CSS, JavaScript and SVG. No external runtime libraries, analytics, fonts, account or database are required. All paths support a GitHub Pages repository subpath.

## Scientific interpretation

These are research estimates, not a global GFA truth dataset. The 2020 level is a converted physical proxy. Sector composition is a conditional allocation. Histories and future paths use shared source-informed rules; the country paths on the homepage are full-fit delivery estimates, not held-out validation predictions.

The factor library contains 43 original candidates plus six static OBAT attributes. It distinguishes actual country inclusion, unavailable factors, period context and annual timing. The one-year construction lag contributes through its combined construction signal rather than as a separate fitted coefficient. GHS-WUP supplies an additional horizontal path outside that 49-factor inventory. Inclusion is not a causal effect or an automatic accuracy improvement.

The 37 structural scenario envelopes have no calibrated probability coverage. The global envelope was formed from coherent joint scenario totals, not sums of country-specific minima/maxima. No global accuracy percentage, 2030 observed outcome, calibrated GFA confidence interval or institutional approval is claimed. Earlier pipeline defaults and all frozen model outputs remain unchanged.

## Source export and checking

In the complete research project, run:

```sh
python3 scripts/build_country_explorer.py
node tests/test_country_explorer.cjs
python3 -m http.server 8790 --bind 127.0.0.1 --directory research-site
```

The exporter reads frozen inputs without fitting. It verifies the known final CSV and fitted-model hashes, country-year accounting, balanced global sums and unchanged input bytes. The numerical checks exercise interval calculations, CAGR compounding, annual gaps, full-precision CSV output, chart geometry and factor roles. Browser controls and responsive layouts are checked separately.

The public repository contains selected presentation data and the model implementation module, not the complete private source history or raw source lake. Rebuilding the export requires the full research project. The implementation module's project dependencies are not bundled as a standalone executable.

All numbers are nominal year-end estimates. Backcasts cover 2015–2019, the fixed reference is 2020, newer-source-conditioned reconstruction covers 2021–2025, the model-based nowcast is 2026, and conditional forecasts cover 2027–2030. Cross-dataset differences do not establish accuracy when definitions, coverage, conversion or upstream sources overlap.
