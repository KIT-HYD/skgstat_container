import os
import sys
from datetime import datetime as dt
from pprint import pprint
from time import time
import json

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
    np.savetxt('/out/kriging.dat', field)
    np.savetxt('/out/sigma.dat', sigma)

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

    np.savetxt('/out/simulation_mean.dat', sim_mean)
    np.savetxt('/out/simulation_std.dat', sim_std)

    # save variogram for reference
    vario_results(vario)

elif toolname == 'sample':
    # get the field data
    try:
        field = parse_array_input(kwargs['field'])
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
    np.savetxt('/out/coordinates.dat', coordinates)
    np.savetxt('/out/values.dat', values)

elif toolname == 'cross-validation':
    # get the parameters
    try:
        coords = kwargs['coordinates']
        values = kwargs['values']
        vario_params = kwargs['variogram']
        measure = kwargs.get('measure', 'rmse')
    except Exception as e:
        print(str(e))
        sys.exit(1)

    # build the variogram
    print('Estimating variogram...')
    vario = skg.Variogram(coords, values, **vario_params)
    print(vario)

    # get the cov-model
    covmodel = vario.to_gstools()

    # get the number
    n = len(coords)
    err = []

    # do the cross validation
    t1 = time()
    for it in range(n):
        x = np.array([c for i, c in enumerate(coords) if i != it]).T
        y = [v for i, v in enumerate(values) if i != it]

        # build the kriging
        krige = gs.Krige(covmodel, x, y, fit_variogram=False)
        y_pred = krige(coords[it].T)

        err.append(y_pred - values[it])
    t2 =  time()
    
    # calculate the measure
    if measure.lower() == 'rmse':
        m = np.sqrt(np.mean(np.power(err, 2)))
    elif measure.lower() == 'mad':
        m = np.median(np.abs(err))
    else:
        m = np.mean(np.abs(err))
    
    # print results
    print(f'Took {np.round(t2 - t1, 2)} seconds.')
    print(f'{measure.upper()}: {m}')

    # also to json
    with open('/out/cross_validation.json', 'w') as f:
        json.dump({measure: m}, f)

    # print the variogram results
    vario_results(vario)

# Tool is unknown
else:
    print(f"[{dt.now().isocalendar()}] Either no TOOL_RUN environment variable available, or '{toolname}' is not valid.\n")

