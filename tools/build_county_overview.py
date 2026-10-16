"""Build display-only county concentrations from the full block-group table.

Usage: python tools/build_county_overview.py BLOCK_GROUP_PARQUET COUNTY_SHAPEFILE
Requires geopandas, pandas, numpy, and Shapely >= 2.1 with GEOS >= 3.12.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely


def build_overview(block_group_path, county_path, output_dir):
    bg = gpd.read_parquet(block_group_path).to_crs(3310)
    fields = sorted(c for c in bg.columns if c.startswith('conc_'))
    if not fields or bg.GEOID.duplicated().any():
        raise ValueError('Expected unique block groups and conc_<sector> fields')
    if (bg.covered_area_m2 < 0).any() or not np.isfinite(bg.covered_area_m2).all():
        raise ValueError('Invalid covered-area weights')
    bg['county_fips'] = bg.GEOID.str[:5]
    grouped = bg.groupby('county_fips')
    stats = pd.DataFrame(index=grouped.size().index)
    stats['block_groups'] = grouped.size()
    stats['covered_area_m2'] = grouped.covered_area_m2.sum()
    for field in fields:
        # Current analysis has finite concentrations for every block group.
        # Reject missing values rather than guessing variable-specific weights.
        if not np.isfinite(bg[field]).all():
            raise ValueError(f'{field} needs variable-specific valid-area weights')
        weighted = (bg[field] * bg.covered_area_m2).groupby(bg.county_fips).sum()
        stats[field] = weighted / stats.covered_area_m2.replace(0, np.nan)
    counties = bg[['county_fips', 'geometry']].dissolve(by='county_fips').reset_index()
    # Names are assigned spatially from the supplied county boundaries.
    names = gpd.read_file(county_path).to_crs(3310)
    points = counties.copy()
    points.geometry = points.representative_point()
    matches = gpd.sjoin(points, names[['NAME', 'geometry']], how='left', predicate='within')
    if len(matches) != len(counties) or matches.NAME.isna().any():
        raise ValueError('Expected one county name per county polygon')
    counties['name'] = matches.NAME.to_numpy()
    counties = counties.merge(stats.reset_index(), on='county_fips', validate='one_to_one')
    if len(counties) != 58 or len(bg) != 25589:
        raise ValueError('Expected all 58 counties and 25,589 block groups')
    # Simplify shared boundaries together, after calculating full-resolution means.
    if not shapely.coverage_is_valid(counties.geometry.to_numpy()):
        raise ValueError('County geometry is not a valid coverage')
    counties.geometry = shapely.coverage_simplify(counties.geometry.to_numpy(), 500)
    if not counties.is_valid.all():
        raise ValueError('Invalid simplified overview geometry')
    counties['geography'] = 'county'
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / 'county_concentrations.geojson'
    path.write_text(counties.to_crs(4326).to_json(drop_id=True), encoding='utf-8')
    metadata = {
        'source_array_run': '39994974', 'emissions_year': 2017,
        'census_geography_year': 2020, 'counties': len(counties),
        'block_groups': len(bg), 'units': 'µg/m³', 'sector_fields': fields,
        'weighting': 'sum(block_group_concentration * covered_area_m2) / sum(covered_area_m2)',
        'population_weighted': False, 'display_simplification_metres': 500,
        'display_only': True,
        'source_analysis': 'California block-group sector analysis, array 39994974',
        'county_names': 'California county boundaries supplied to build script',
    }
    (output_dir / 'county_concentrations.metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    print(f'Wrote {len(counties)} counties, {len(fields)} sectors: {path.stat().st_size:,} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('block_group_parquet', type=Path)
    parser.add_argument('county_shapefile', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    build_overview(args.block_group_parquet, args.county_shapefile, args.output_dir)
