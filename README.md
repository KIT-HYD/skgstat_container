# Geostatistical tools container

This repository contains a docker image for geostatistical data processing using standardized input and outputs. 
This is based on the template for a generic containerized Python [tool](https://github.com/vforwater/tool_template_python). 

Currently, there are three tools implemented:

1. Geostatistical variogram estimation
2. Kriging interpolation
3. Geostatistical simulation

In order to run an interpolation or simulation,you need to provide a valid variogram first. The variogram tool is accompanied
by extensive plotting to validate its geospatial robustness. 
Variograms can be calculated for spatially distributed samples, or spatially dense fields. You need to provide either of 
both inputs. If a field is used, it is highly recommended to subsample it instead of resolving all coordinates into a sample.
The tool defaults to a maximum sample size of 1000, which can be disabled by setting the sample_size parameter to -1.

To identify the spatial coordinates, the tool will look for standard column names, namely:
`x, y, lon, lat, longitude, latitude`. It is recommended to use projected data, but in case of field information, the 
tool will reproject to the most likely UTM zone. Samples are never reprojected.

Samples with more than one non-spatial column will be estimated as cross-variograms. Fields with more than one variable 
will yield multiple variograms. If many variograms are estimated, the kriging and simulation tools can iterate over 
many inputs.

## Parameters

The tables below summarize the availble parameters for each of the tools.

### Variogram

| Parameter Name | Description | Data Type |
|---|---|---|
| `n_lags` | Number of separating distance lag classes. Is ignored for bin_funcs [fd, sturges, scott, doane, sqrt] | integer |
| `bin_func` | Function to group the distance matrix into lag classes. | enum |
| `model` | Interpretive theoretical variogram model function to model the covariance | enum |
| `estimator` | Semi-variance estimation method to calculate the empirical variogram | enum |
| `maxlag` | Can be 'median', 'mean', a number < 1 for a ratio of maximum separating distance or a number > 1 for an absolute distance | string |
| `fit_method` |  | enum |
| `use_nugget` | Enable the nugget parameter. Defaults to False, which will set the nugget parameter to 0. | bool |
| `fit_range` | Only valid if fit_method='manual'. The variogram effective range. | float |
| `fit_sill` | Only valid if fit_method='manual'. The variogram sill. | float |
| `fit_nugget` | Only valid if fit_method='manual'. The variogram nugget. | float |
| `fit_sigma` | Use a distance dependent weight on fits to favor closer bins. Do not set for | enum |
| `sample_size` | Number of data points to use for the empirical variogram. This is used as a maximum sample size. If the passed data is larger, a random subsample will be taken from the supplied sample data. If instead a field is used, the field will be sub-sampled on along the spatial dimensions. If the field has a temporal dimension, it will be aggregated. If you set the sample_size to a **nagative value** (-1), the entire input data will be used, which may result in long runtimes. | integer |
| `field` | Input data as a field, like a NetCDF variable or a GeoTiff. If these files get too large, the tool will operate on a sample. You can also force the sample, by setting a positive sample size. | file (extension) |
| `sample` | Input data as a spatial sample, like a CSV or parquet file. The tool will check for spatial columns named ('x', 'y', 'lon', 'lat', 'longitude', 'latitude') and use the first non-spatial column as the value column. If there is more than one non-spatial column, a cross-variogram is calculated. | file (extension) |

### Kriging

| Parameter Name | Description | Data Type |
|---|---|---|
| `grid` | The grid size needs to be defined by a string like NNxMM, where NN are the number of rows and MM the number of columns | string |
| `algorithm` |  | enum |
| `mean` | Real Mean value of the field. Only needed for Simple Kringing. | float |
| `drift_functions` | Predefined drift function. Only needed for Universal Kriging. | enum |
| `variogram` | A JSON file containing the variogram parameters as returned by Variogram.describe()['params']. You can use the 'variogram' tool to generate such a file in the output. You can only use the | file (extension) |

### Simulation

| Parameter Name | Description | Data Type |
|---|---|---|
| `grid` | The grid size needs to be defined by a string like NNxMM, where NN are the number of rows and MM the number of columns | string |
| `n_simulations` | Number of simulations to run. Defaults to 100 | integer |
| `seed` | Seed for the random number generator. Defaults to 42. It is highly recommended to change this number on every run | integer |
| `variogram` | A JSON file containing the variogram parameters as returned by Variogram.describe()['params']. You can use the 'variogram' tool to generate such a file in the output. You can only use the | file (extension) |


## Why does this container look so weird?

This tool uses the [Tool-Specs](https://vforwater.github.io/tool-specs/) to standardize the input and output of the tool.
It is based on the [Python template](https://github.com/vforwater/tool_template_python).

The internal file structure is as follows:

```
/
|- in/
|  |- inputs.json
|- out/
|  |- ...
|- src/
|  |- tool.yml
|  |- run.py
```

* `inputs.json` are parameters. Whichever framework runs the container, this is how parameters are passed.
* `tool.yml` is the tool specification. It contains metadata about the scope of the tool, the number of endpoints (functions) and their parameters
* `run.py` is the tool itself, or a Python script that handles the execution. It has to capture all outputs and either `print` them to console or create files in `/out`

## How to use the image?

You pull this image from Github:

```
docker pull ghcr.io/vforwater/tbr_skgstat
```

Alternatively, you can build the image from within the root of this repo by
```
docker build -t tbr_skgstat .
```

Use any tag you like. If you want to run and manage the container with [toolbox-runner](https://github.com/hydrocode-de/tool-runner) they should be prefixed by `tbr_` to be recognized. 

Alternatively, you can use GoRun (link and info will follow).

## How to run?

If you do not use a package like GoRun or toolbox-runner to manage the docker images, you need 
to populate the `/in/inputs.json` with the parameters for the tool, copy the input data into the `/in` mount point
and reference the data in the `/in/inputs.json`.

To invoke the docker container directly run something similar to:
```
docker run --rm -it -v /path/to/local/in:/in -v /path/to/local/out:/out -e TOOL_RUN=variogram tbr_skgstat
```

Then, the output will be in your local out and based on your local input folder. Stdout and Stderr are also connected to the host. A Gorun based example will follow in a future release.
