# base image
FROM python:3.10.8

# install geostatistical libraries
RUN pip install scikit-gstat==1.0.2 gstools==1.4.0 plotly==5.11.0

# install the Python toolbox-runner
RUN pip install toolbox-runner==0.5.1

# create the tool input structure
RUN mkdir /in
COPY ./in /in
RUN mkdir /out
RUN mkdir /src
COPY ./src /src

WORKDIR /src
CMD ["python", "run.py"]
