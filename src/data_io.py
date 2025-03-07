from typing import Generator
from pathlib import Path

import pandas as pd
import rioxarray as rio
import xarray as xr
import numpy as np
from json2args.logger import logger


GEO_STANDARD_NAMES = ['x', 'y', 'lon', 'lat', 'longitude', 'latitude', 'spatial_ref']
TIME_STANDARD_NAMES = ['time', 'date', 'datetime']

def _random_sample(coords: np.ndarray, values: np.ndarray, sample_size: int) -> tuple[np.ndarray, np.ndarray]:
    if sample_size > 0 and sample_size < len(values):
        idx = np.random.choice(len(values), sample_size, replace=False)
        coords = coords[idx]
        values = values[idx]

    return coords.copy(), values.copy()

def iter_samples(datapaths: dict[str, str], sample_size: int) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:
    if 'sample' in datapaths:
        p = Path(datapaths['sample'])
        if p.suffix == '.csv':
            df = pd.read_csv(p)
        elif p.suffix == '.parquet':
            df = pd.read_parquet(p)
        else:
            raise ValueError(f"Cannot load data from {p} as it is not a supported file format (.csv, .parquet).")
        
        df.columns = [name.lower() for name in df.columns]
        if 'x' in df.columns and 'y' in df.columns:
            coords = df[['x', 'y']].values
        elif 'lon' in df.columns and 'lat' in df.columns:
            coords = df[['lon', 'lat']].values
        elif 'longitude' in df.columns and 'latitude' in df.columns:
            coords = df[['longitude', 'latitude']].values
        else:
            raise ValueError(f"Cannot find coordinates in the sample file {p}. You can specify them manually.")
        
        value_names = [name for name in df.columns if name not in GEO_STANDARD_NAMES]
        values = df[value_names].values
        if len(value_names) > 0:
            if values.shape[1] == 1:
                values = values.ravel() 

            yield _random_sample(coords, values, sample_size), "_".join(value_names)

    elif 'field' in datapaths:
        p = Path(datapaths['field'])
        if p.suffix == '.nc':
            if '*' in str(p):
                ds = xr.open_mfdataset(p, decode_coords='all', mask_and_scale=True)
            else:
                ds = xr.open_dataset(p, decode_coords='all', mask_and_scale=True)
        elif p.suffix.lower() == '.tiff' or p.suffix.lower() == '.tif':
            ds = rio.open_rasterio(p, mask_and_scale=True)

        if ds.rio.crs is None:
            ds.rio.write_crs("EPSG:4326", inplace=True)
        if ds.rio.crs.is_geographic:
            tgt = ds.rio.estimate_utm_crs() 
            if tgt is None:
                tgt = rio.crs.CRS.from_epsg(3857)
            #ds.rio.reproject(dst_crs=tgt, inplace=True)
        
        
        for var in ds.variables:
            if var.lower() in GEO_STANDARD_NAMES or var in TIME_STANDARD_NAMES:
                continue
            
            if not all([d.lower() in GEO_STANDARD_NAMES or d.lower() in TIME_STANDARD_NAMES for d in ds[var].dims]): 
                logger.debug(f"Skip variable {var} as it has dimensions, that are not geographic nor time. Dimensions: {ds[var].dims}; You may ravel the data first.")
                continue
            
            if ds[var].rio.crs.is_geographic:
                arr = ds[var].rio.reproject(dst_crs=tgt)
            else:
                arr = ds[var]
            
            dims = (arr.rio.x_dim, arr.rio.y_dim, )
            time_ax = next(filter(lambda d: d.lower() in TIME_STANDARD_NAMES, arr.dims), None)
            if time_ax is None:
                df = arr.to_dataframe().reset_index()

                coords = df[[*dims]].values
                values = df[var].values

                yield _random_sample(coords, values, sample_size), var
            
            else:
                for i in range(arr.sizes[time_ax]):
                    df = arr.isel(**{time_ax: i}).to_dataframe().reset_index()

                    coords = df[[*dims]].values
                    values = df[var].values

                    yield _random_sample(coords, values, sample_size), f"{var}_timeidx_{i + 1}"
    else:
        raise ValueError(f"No data was defined in the input. Please provide either a field or a sample. (datapaths={datapaths})")


        



