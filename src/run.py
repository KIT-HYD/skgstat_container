import os
import sys
import json
from datetime import datetime as dt

import skgstat as skg
import gstools as gs
from plotly.io import to_json
import numpy as np
from toolbox_runner.parameter import parse_parameter

# parse parameters
kwargs = parse_parameter()

# check if a toolname was set in env
toolname = os.environ.get('TOOL_RUN', 'variogram').lower()

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
        to_json(fig, '/out/plotly_variogram.json')

    # create a PDF
    if 'pdf' in add_result:
        skg.plotting.backend('matplotlib')
        fig = vario.plot()
        fig.savefig('/out/variogram.pdf', dpi=200)

# switch the tool
if toolname == 'variogram':
    # handle maxlag settings
    if 'maxlag' in kwargs and kwargs['maxlag'] not in ('mean', 'median'):
        kwargs['maxlag'] = float(kwargs['maxlag'])
    
    # handle fit_sigma settings
    if 'fit_sigma' in kwargs and kwargs['fit_sigma'] is None:
        del kwargs['fit_sigma']
    
    # estimate the variogram
    vario = skg.Variogram(**kwargs)

    # create the output
    vario_results(vario)

# Kriging tool
elif toolname == 'kriging':
    # get the parameters
    try:
        coords = kwargs['coordinates']
        values = kwargs['values']
        vario_params = kwargs['variogram']
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # build the variogram
    print('Estimating variogram...')
    vario = skg.Variogram(coords, values, **vario_params)
    print(vario)

    # build the grid
    try:
        _x, _y = kwargs['grid'].split('x')
        _x = int(_x)
        _y = int(_y)
    except Exception as e:
        print(str(e))
        sys.exit(1)
    x = np.linspace(vario.coordinates[:,0].min(), vario.coordinates[:,0].max(), _x)
    y = np.linspace(vario.coordinates[:,1].min(), vario.coordinates[:,1].max(), _y)

    # get the kriging algorithm
    if kwargs['algorithm'] == 'simple':
        args = {'mean': kwargs['mean']}
    elif kwargs['algorithm'] == 'universal':
        args = {'drift_function': kwargs['drift_function']}
    else:
        args = {'unbiased': True}
    
    # interpolate
    print('Start interpolation...', end='')
    t1 = dt.now()
    krige = vario.to_gs_krige(**args)
    field, sigma = krige.structured((x, y))
    t2 = dt.now()
    print(f'done. Took {round((t2 - t1).total_seconds(), 2)} seconds.')

    # write results
    np.savetxt('/out/kriging.mat', field)
    np.savetxt('/out/sigma.mat', sigma)

    # create the output
    vario_results(vario)

elif toolname == 'simulation':
    # get the parameters
    try:
        coords = kwargs['coordinates']
        values = kwargs['values']
        vario_params = kwargs['variogram']
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # build the variogram
    print('Estimating variogram...')
    vario = skg.Variogram(coords, values, **vario_params)
    print(vario)

    # build the grid
    try:
        dims = [int(_) for _ in kwargs['grid'].split('x')]
        assert len(dims) == vario.coordinates.shape[1]
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # build the ranges
    coord_mesh = []
    coords = vario.coordinates
    for d, dim in enumerate(dims):
        coord_mesh.append([np.linspace(coords[:, d].min(), coords[:,d].max(), dim)])

    # get a kriging instance and a random field generator
    krige = vario.to_gs_krige()
    cond_srf = gs.CondSRF(krige)

    # build the result container
    fields = []

    # get the N keyword, defaults to 100
    N = kwargs.get('n_simulations', 100)
    seed = kwargs.get('seed', 42)
    
    print(f'Starting {N} iterations seeded {seed}')
    for i in range(N):
        field = cond_srf.structured(coord_mesh, seed=seed + i)
        fields.append(field)

        print(f"[{i + 1}/{N}]")
    
    # TODO: enable saving all simulations into a netCDF
    ndims = len(dims)
    stack = np.stack(fields, axis=ndims)

    # create results
    sim_mean = np.mean(stack, axis=ndims)
    sim_std = np.std(stack, axis=ndims)

    np.savetxt('/out/simulation_mean.mat', sim_mean)
    np.savetxt('/out/simulation_std.mat', sim_std)

    # save variogram for reference
    vario_results(vario)

else:
    with open('/out/error.log', 'w') as f:
        f.write(f"[{dt.now().isocalendar()}] Either no TOOL_RUN environment variable available, or '{toolname}' is not valid.\n")