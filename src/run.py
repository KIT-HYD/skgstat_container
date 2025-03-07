import os
import sys
from datetime import datetime as dt
from time import time
import json

import skgstat as skg
import gstools as gs
import numpy as np
from json2args import get_parameter
from json2args.logger import logger
from json2args.data import get_data_paths

from data_io import iter_samples
from tools import process_variogram, vario_results, read_saved_variogram, build_grid

# parse parameters
kwargs = get_parameter(typed=True)
datapaths = get_data_paths()

# check if a toolname was set in env
toolname = os.environ.get('TOOL_RUN', 'variogram').lower()

# switch the tool
if toolname == 'variogram':
    logger.info("#TOOL START - variogram")
    logger.debug(f"Parameters: {kwargs}")
    logger.debug(f"Datapaths: {datapaths}")
    
    for (coords, values), name in iter_samples(datapaths, sample_size=kwargs.sample_size):
        t1 = time()
        try:
            vario = process_variogram(coords, values, kwargs)
        except Exception as e:
            logger.error(f"Error while processing variogram: {e}")
            continue
        
        logger.info(f"Estimated a variogram for {name} in {time() - t1:.2f} seconds.")
        logger.info(str(vario))
        logger.debug(f"Variogram: {vario.describe()}")
        
        # create the output
        vario_results(vario, name)
    logger.info("#TOOL END - variogram")

# Kriging tool
elif toolname == 'kriging':
    logger.info("#TOOL START - kriging")
    logger.debug(f"Parameters: {kwargs}")
    logger.debug(f"Datapaths: {datapaths}")

    t1 = time()

    # for each variogram
    for vario, name in read_saved_variogram(datapaths['variogram']):
        # build the grid
        try:
            coord_mesh = build_grid(vario, kwargs.grid)
            logger.info(f"Build interpolation grid with {len(coord_mesh)} axes.")
        except Exception as e:
            logger.error(f"Error while building interpolation grid: {e}")
            continue
    
        # get the kriging algorithm
        if kwargs.algorithm == 'simple':
            args = {'mean': kwargs['mean']}
        elif kwargs.algorithm == 'universal':
            args = {'drift_function': kwargs['drift_function']}
        else:
            args = {'unbiased': True}
        logger.debug(f"Derived Kriging settings: {args}")
    
        # interpolate
        try: 
            t2 = time()
            krige = vario.to_gs_krige(**args)
            field, sigma = krige.structured(coord_mesh)
            t3 = time()
        except Exception as e:
            logger.error(f"Error while interpolating {name}: {e}")
            continue
        logger.info(f"Interpolated {name} in {t3 - t2:.2f} seconds.")

        # write results
        np.savetxt(f"/out/{name}_kriging.dat", field)
        np.savetxt(f"/out/{name}_sigma.dat", sigma)
    logger.info(f"Total runtime: {time() - t1:.2f} seconds.")
    logger.info("#TOOL END - kriging")


elif toolname == 'simulation':
    raise NotImplementedError

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

# Tool is unknown
else:
    print(f"[{dt.now().isocalendar()}] Either no TOOL_RUN environment variable available, or '{toolname}' is not valid.\n")

