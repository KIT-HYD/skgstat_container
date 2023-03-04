import json

from plotly.io import write_json
import skgstat as skg
import numpy as np
import xarray as xr

# helper functions
def vario_results(vario: skg.Variogram, add_result=['vario', 'params', 'html', 'pdf']):
    # get the variogram as json
    result = vario.describe()
    vario_param = result['params']

    # json result
    if 'vario' in add_result:
        with open('/out/result.json', 'w') as f:
            json.dump(result, f, indent=4)
    
    # parameters result
    if 'params' in add_result:
        with open('/out/variogram.json', 'w') as f:
            json.dump(vario_param, f, indent=4)
    
    # create a interactive figure
    if 'html' in add_result:
        skg.plotting.backend('plotly')
        fig = vario.plot()
        fig.write_html('/out/variogram.html')
        write_json(fig, '/out/variogram.plotly.json')

    # create a PDF
    if 'pdf' in add_result:
        skg.plotting.backend('matplotlib')
        fig = vario.plot()
        fig.savefig('/out/variogram.pdf', dpi=200)


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

def parse_array_input(arr, field_name=None):
    if isinstance(arr, np.ndarray):
        return arr
    if isinstance(arr, (list, tuple)):
        return np.asarray(arr)
    if isinstance(arr, xr.Dataset):
        # get the variable name
        if field_name is None:
            field_name =  list(arr.data_vars.keys())[0]
        return arr[field_name].values
    
    # don't know
    return arr
