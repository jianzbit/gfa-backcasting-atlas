# Global Floorspace Atlas

English interactive presentation of Indicator 1.1 v16 Total estimates with the adopted four-epoch GHSL sector allocation, updated 21 October 2026.

The displayed Residential/Non-residential split now follows qualified GHS-BUILT-V R2023A relative volume changes at 2015, 2020, 2025 and 2030. Every country-year Total and every 2020 sector anchor is preserved. Intermediate volumes are interpolated; 2025/2030 source epochs are projections.191 historical and189 future country paths use the new allocation; unsupported countries retain the original v16 split with explicit source roles. This is a conditional research allocation, not a claim of established accuracy improvement or a change to the canonical BIT pipeline.

The homepage covers 195 country series from 2015 to 2030. Users can select Total, Residential or Non-residential GFA and any valid start/end years. The calculator reports endpoint floorspace, net area change, cumulative growth and compound annual growth. Charts show levels, annual changes, annual growth rates or a 2020-normalized index. Country CSV and standalone SVG downloads retain explicit units and estimate roles.

The primary global aggregate contains the same 194 countries at every date. State of Palestine is a separately labeled source-conditioned supplement. Its 2023–2030 values are a counterfactual unadjusted stock baseline without measured conflict destruction/reconstruction; they are excluded from the primary global total.

## Contents

- `index.html`, `explorer.css`, `explorer.js`: current country explorer, methods, factors and evidence.
- `data/explorer-data.js`: full-precision central values, supplied sensitivity envelopes and actual country factor roles.
- `downloads/v16-*`: unchanged research CSV/specification/source exports and provenance.
- `downloads/v16-ghsl-composition-*`: adopted country/world values, recalculated scenario ranges, source roles, coverage, mixed validation, allocation code and provenance.
- `downloads/v16-atlas-before-ghsl-composition.zip`: byte-preserved complete previous Atlas snapshot.
- `comparison/`: cross-dataset disagreement tables and interactive report, including native physical quantities and explicitly conditional area equivalents.
- `history.html`: preserved 9 October 2026 atlas of fourteen early model variants. Its archived data, scores and assets retain their earlier scope.
- `history-README.md`: documentation for that earlier snapshot.

The website uses local HTML, CSS, JavaScript and SVG. No external runtime libraries, analytics, fonts, account or database are required. All paths support a GitHub Pages repository subpath.

## Scientific interpretation

These are research estimates, not a global GFA truth dataset. The 2020 level is a converted physical proxy. Sector composition is a conditional allocation. Histories and future paths use shared source-informed rules; the country paths on the homepage are full-fit delivery estimates, not held-out validation predictions.

The factor library contains 43 original candidates plus six static OBAT attributes. It distinguishes actual country inclusion, unavailable factors, period context and annual timing. The one-year construction lag contributes through its combined construction signal rather than as a separate fitted coefficient. GHS-WUP supplies an additional horizontal path outside that 49-factor inventory. Inclusion is not a causal effect or an automatic accuracy improvement.

All 37 structural scenario paths were passed through the same adopted allocation using their own2020sector shares before ranges were recomputed. The global envelope is formed from coherent joint scenario sums, not sums of country-specific minima/maxima. These ranges condition on the selected GHSL paths and have no calibrated probability coverage. No global accuracy percentage,2030observed outcome, calibrated GFA confidence interval or institutional approval is claimed. All earlier frozen source/model outputs and old downloads remain unchanged.

Existing native residential-change diagnostics are mixed: seven-country LOCO disagreement1.735→1.804 (worse), six nontraining five-year intervals4.389→4.343 (better), LVA/NLD0.639→0.544 (better). These are previously exposed native references, not definition-aligned global GFA accuracy. The adverse result remains visible in the website evidence section and downloads.

## Source export and checking

In the complete research project, run:

```sh
python3 scripts/build_dynamic_composition_atlas.py
node tests/test_country_explorer.cjs
python3 -m unittest tests.test_dynamic_composition_atlas
python3 -m http.server 8790 --bind 127.0.0.1 --directory research-site
```

The exporter reads frozen inputs without fitting. It verifies the known final CSV and fitted-model hashes, country-year accounting, balanced global sums and unchanged input bytes. The numerical checks exercise interval calculations, CAGR compounding, annual gaps, full-precision CSV output, chart geometry and factor roles. Browser controls and responsive layouts are checked separately.

The public repository contains selected presentation data and the model implementation module, not the complete private source history or raw source lake. Rebuilding the export requires the full research project. The implementation module's project dependencies are not bundled as a standalone executable.

All numbers are nominal year-end estimates. Backcasts cover 2015–2019, the fixed reference is 2020, newer-source-conditioned reconstruction covers 2021–2025, the model-based nowcast is 2026, and conditional forecasts cover 2027–2030. Cross-dataset differences do not establish accuracy when definitions, coverage, conversion or upstream sources overlap.
