# us-inmap_dashboard-play
## Map scales

The initial view fits all California. Below zoom 7, `data/county_concentrations.geojson`
provides county area-weighted total PM2.5 concentrations. At zoom 7 and above,
the existing PMTiles source provides Census block groups. The geography badge
and hover tooltip identify the active scale. Sector selection updates both layers.

County concentrations are calculated from the full-resolution block-group analysis:
`sum(concentration * covered_area_m2) / sum(covered_area_m2)` within each county.
This is an area-weighted county mean, not a population-weighted exposure statistic.
The input has complete coverage and finite values for every block group. Display
geometry is simplified at 500 m only after values are calculated, preserving shared
county borders. The overview includes all 58 counties and all 19 raw sector fields;
the dashboard's existing display groups continue to exclude the two wildland-fire
sectors. The overview is approximately 652 KB uncompressed and is served with the
site; no change to the external PMTiles archive is required.

To regenerate the overview with GeoPandas, pandas, NumPy, and Shapely >= 2.1
(GEOS >= 3.12):

```bash
python tools/build_county_overview.py \
  /path/to/block_group_total_pm25_by_sector.parquet \
  /path/to/CaCounty.shp
```

The metadata sidecar documents the source run, weights, fields, and simplification.
The existing component selectors and summary statistics are separate prototype
work; this change does not add component data or recompute dashboard statistics.
