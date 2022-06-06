ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION}
LABEL maintainer='Mirko Mälicke'

# build the structure
RUN mkdir -p /src/data
RUN mkdir -p /src/config

# copy the sources
COPY ./streamlit_app.py /src/streamlit_app.py
COPY ./BASE_DATA.json /src/BASE_DATA.json

# COPY the packaging
COPY ./requirements.txt /src/requirements.txt

# COPY only the shared data as fallback
COPY ./data/shared_backup.db /src/data/shared.db

# build the package
RUN pip install --upgrade pip
RUN pip install -r /src/requirements.txt

# create the entrypoint
WORKDIR /src
ENTRYPOINT ["streamlit", "run"]
CMD ["streamlit_app.py"]