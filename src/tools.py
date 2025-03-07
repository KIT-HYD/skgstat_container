from typing import Generator
import json
import pickle
from pathlib import Path

import numpy as np
import skgstat as skg
from plotly.io import write_json

def process_variogram(coords: np.ndarray, values: np.ndarray, kwargs) -> skg.Variogram:
    if kwargs.maxlag is not None:
        if kwargs.maxlag in ('median', 'mean'):
            maxlag = kwargs.maxlag
        else:
            maxlag = float(kwargs.maxlag)
    else:
        maxlag = None

    return skg.Variogram(
        coords,
        values,
        bin_func=kwargs.bin_func,
        n_lags=kwargs.n_lags,
        model=kwargs.model,
        estimator=kwargs.estimator,
        maxlag=maxlag,
        use_nugget=kwargs.use_nugget,
        normalize=False,
        fit_method=kwargs.fit_method,
        fit_sigma=None if kwargs.fit_sigma.lower() == 'none' else kwargs.fit_sigma,
        fit_range=kwargs.fit_range,
        fit_sill=kwargs.fit_sill,
        fit_nugget=kwargs.fit_nugget,
    )

def vario_results(vario: skg.Variogram, name: str, add_result=['vario', 'params', 'html', 'pdf']):
    # get the variogram as json
    result = vario.describe()
    vario_param = result['params']

    # parameters result
    if 'params' in add_result:
        with open(f"/out/{name}_variogram_params.json", 'w') as f:
            json.dump(vario_param, f, indent=4)

    if 'vario' in add_result:
        with open(f"/out/{name}_variogram.pkl", 'wb') as f:
            pickle.dump(vario, f)
        with open(f"/out/{name}_variogram.json", 'w') as f:
            json.dump({
                'variogram': result,
                'coordinates': vario.coordinates.tolist(),
                'values': vario.values.tolist(),
            }, f, indent=4)
    
    # create a interactive figure
    if 'html' in add_result:
        skg.plotting.backend('plotly')
        fig = vario.plot(show=False)
        fig.write_html(f"/out/{name}_variogram.html")
        write_json(fig, f"/out/{name}_variogram.plotly.json")

        fig = vario.distance_difference_plot(show=False)
        fig.write_html(f"/out/{name}_variogram_distance_difference.html")
        write_json(fig, f"/out/{name}_variogram_distance_difference.plotly.json")

        fig = vario.scattergram(show=False)
        fig.write_html(f"/out/{name}_variogram_scattergram.html")
        write_json(fig, f"/out/{name}_variogram_scattergram.plotly.json")

    # create a PDF
    if 'pdf' in add_result:
        skg.plotting.backend('matplotlib')
        fig = vario.plot(show=False)
        fig.savefig(f"/out/{name}_variogram.pdf", dpi=200)

        fig = vario.distance_difference_plot(show=False)
        fig.savefig(f"/out/{name}_variogram_distance_difference.pdf", dpi=200)
        
        fig = vario.scattergram(show=False)
        fig.savefig(f"/out/{name}_variogram_scattergram.pdf", dpi=200)


def read_saved_variogram(path: str) -> Generator[skg.Variogram, None, None]:
    path = Path(path)
    for fname in path.parent.glob(path.name):
        if fname.suffix == '.pkl':
            with open(fname, 'rb') as f:
                yield pickle.load(f), fname.stem
        elif fname.suffix == '.json':
            with open(fname, 'r') as f:
                payload = json.load(f)

                coords = np.asarray(payload['coordinates'])
                values = np.asarray(payload['values'])
                var = payload['variogram']

                yield skg.Variogram(coords, values, **var.get('params', {})), fname.stem
        else:
            raise ValueError(f"Cannot load variogram from {path} as it is not a supported file format (.pkl, .json).")


def build_grid(vario: skg.Variogram, grid_spec: str):
    # get the dimensions
    dims = [int(_) for _ in grid_spec.split('x')]
    coords = vario.coordinates
    if len(dims) != coords.shape[1]:
        raise ValueError(f"The grid specs do not match the input data. Variogram dims: {coords.shape[1]}; Grid dims: {len(dims)}")
    
    # build the ranges
    coord_mesh = []
    for d, dim in enumerate(dims):
        coord_mesh.append([np.linspace(coords[:,d].min(), coords[:,d].max(), dim)])
    
    return coord_mesh