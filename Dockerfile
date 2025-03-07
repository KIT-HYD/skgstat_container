# base image
FROM python:3.13.1

#RUN apt-get update && apt-get install -y binutils gdal-bin libgdal-dev && \
#    pip install --upgrade pip && \
#    pip install GDAL==$(gdal-config --version | awk -F'[.]' '{print $1"."$2}')
RUN apt-get update && apt-get install -y binutils gdal-bin libgdal-dev && \
    pip install --upgrade pip

# install geostatistical libraries
RUN pip install scikit-gstat==1.0.19 \
    gstools \
    plotly \
    "xarray[complete]" \
    netcdf4 \
    gstatsim==1.0.6 \
    "json2args[data]==0.7.0" \
    tqdm \
    rioxarray


# uncomment for development
RUN pip install ipython

# create the tool input structure
RUN mkdir /in
COPY ./in /in
RUN mkdir /out
RUN mkdir /src
COPY ./src /src

# copy the citation file - looks funny to make COPY not fail if the file is not there
COPY ./CITATION.cf[f] /src/CITATION.cff

WORKDIR /src
CMD ["python", "run.py"]
