# uncertain_geostatistics
Streamlit application to inspect uncertainty propagation in geostatisics

Use the docker image to deploy the application

```bash
docker run -d -i -p 8501:8501 --rm -v /path/to/uncertain_geostatistics/data:/src/data -v /path/to/uncertain_geostatistics/config:/src/config ghcr.io/hydrocode-de/uncertain_geostatistics
```
