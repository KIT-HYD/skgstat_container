import os
import sys
from datetime import datetime as dt
from pprint import pprint

import skgstat as skg
import gstools as gs
import numpy as np
import progressbar
from json2args import get_parameter
from skgstat_uncertainty.processor import sampling

from tool_lib import vario_results, build_grid, parse_array_input

# parse parameters
kwargs = get_parameter()

# check if a toolname was set in env
toolname = os.environ.get('TOOL_RUN', 'variogram').lower()

# switch the tool
if toolname == 'variogram':
    # handle maxlag settings
    if 'maxlag' in kwargs and kwargs['maxlag'] not in ('mean', 'median'):
        kwargs['maxlag'] = float(kwargs['maxlag'])
    
    # handle fit_sigma settings
    if 'fit_sigma' in kwargs and kwargs['fit_sigma'] is None:
        del kwargs['fit_sigma']
    
    print('Estimating a variogram useing parameters:')
    pprint(kwargs)

    # estimate the variogram
    vario = skg.Variogram(**kwargs)

    print('done.')
    print(vario)

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
    # TODO: - make this work in ND, not only 2d - see simulation
    try:
        coord_mesh = build_grid(vario, kwargs['grid'])
    except Exception as e:
        print(str(e))
        sys.exit(1)
    

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
    field, sigma = krige.structured(coord_mesh)
    t2 = dt.now()
    print(f'done. Took {round((t2 - t1).total_seconds(), 2)} seconds.')

    # write results
    np.savetxt('/out/kriging.mat', field)
    np.savetxt('/out/sigma.mat', sigma)

    # create the output
    vario_results(vario)

# TODO: add some profiling 
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
        coord_mesh = build_grid(vario, kwargs['grid'])
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # get a kriging instance and a random field generator
    krige = vario.to_gs_krige()
    cond_srf = gs.CondSRF(krige)

    # build the result container
    fields = []

    # get the N keyword, defaults to 100
    N = kwargs.get('n_simulations', 100)
    seed = kwargs.get('seed', 42)
    
    print(f'Starting {N} iterations seeded {seed}')
    for i in progressbar.progressbar(range(N)):
        field = cond_srf.structured(coord_mesh, seed=seed + i)
        fields.append(field)
    
    # TODO: enable saving all simulations into a netCDF
    ndims = len(coord_mesh)
    stack = np.stack(fields, axis=ndims)

    # create results
    sim_mean = np.mean(stack, axis=ndims)
    sim_std = np.std(stack, axis=ndims)

    np.savetxt('/out/simulation_mean.mat', sim_mean)
    np.savetxt('/out/simulation_std.mat', sim_std)

    # save variogram for reference
    vario_results(vario)

elif toolname == 'sample':
    # get the field data
    try:
        field = parse_array_input(kwargs['field'], )
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # get the parameters
    try:
        method = kwargs.get('method', 'random')
        args = dict()
        args['N'] = kwargs['sample_size']
        if method.lower() == 'random':
            args['seed'] = kwargs.get('seed')
        elif method.lower() == 'grid':
            # build grid options
            if 'spacing' in kwargs:
                args['spacing'] = kwargs['spacing']
            elif 'shape' in kwargs:
                args['shape'] = kwargs['shape']
            else:
                raise ValueError("Either 'spacing' or 'shape' has to be set for grid sampling.")
            
            # offset
            args['offset'] = kwargs.get('offset')
        else:
            raise ValueError(f"The sampling method '{method}' is not known.")
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # all args are in - do the sampling
    print('Creating sample...', end='')
    if method.lower() == 'random':
        coordinates, values = sampling.random(field, **args)
    else:
        coordinates, values = sampling.grid(field, **args)
    print('done.')

    # save
    np.savetxt('/out/coordinates.mat', coordinates)
    np.savetxt('/out/values.mat', values)

# Tool is unknown
else:
    with open('/out/error.log', 'w') as f:
        f.write(f"[{dt.now().isocalendar()}] Either no TOOL_RUN environment variable available, or '{toolname}' is not valid.\n")
