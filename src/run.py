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
from tqdm import tqdm

from data_io import iter_samples
from tools import process_variogram, vario_results, read_saved_variogram, build_grid, build_simulation_nc

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
    logger.info("#TOOL START - simulation")
    logger.debug(f"Parameters: {kwargs}")
    logger.debug(f"Datapaths: {datapaths}")

    t1 = time()

    for (vario, name) in read_saved_variogram(datapaths['variogram']):
        # build the grid
        try:
            coord_mesh = build_grid(vario, kwargs.grid)
            logger.info(f"Build interpolation grid with {len(coord_mesh)} axes.")
        except Exception as e:
            logger.error(f"Error while building interpolation grid: {e}")
            continue
        
        # setup a kriging for the incompressible filed interpolation
        try:
            krige = vario.to_gs_krige()
            cond_srf = gs.CondSRF(krige)
            logger.debug(f"Use {krige} to create a conditioned spatial random field: {cond_srf}")
        except Exception as e:
            logger.error(f"Error while initializing the Kriging and SRF: {e}")
            continue
        
        t2 = time()
        logger.info(f"Start {kwargs.n_simulations} for {name}...")
        for n_simulation in tqdm(range(kwargs.n_simulations), total=kwargs.n_simulations):
            field = cond_srf.structured(coord_mesh, seed=kwargs.seed + n_simulation)
            build_simulation_nc(field, coord_mesh, n_simulation, name)

        t3 = time()
        logger.info(f"Finished simulation of {n_simulation} fields for {name} in {t3 - t2:.2f} seconds.")

    logger.info(f"Total runtime: {time() - t1:.2f} seconds.")
    logger.info("#TOOL END - simulation")


# Tool is unknown
else:
    print(f"[{dt.now().isocalendar()}] Either no TOOL_RUN environment variable available, or '{toolname}' is not valid.\n")

