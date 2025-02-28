Script will generate collection and overlay files for Kometa. Collection is used for next airing status ordered by date. 

# Collection on Home
<img src="https://zipline.rlvd.eu/u/eKH4fr.png">

# Some status examples
<img src="https://zipline.rlvd.eu/u/WHsD5C.png" width="415">&nbsp;
<img src="https://zipline.rlvd.eu/u/zIbynV.png" width="200">&nbsp;
<img src="https://zipline.rlvd.eu/u/4bY6B9.png" width="415">&nbsp;
<img src="https://zipline.rlvd.eu/u/ZcWejl.png" width="200">

# Usage
Add necessary data into the config yml. Add the py as a cronjob, for example:

```2 0 * * * python3 /root/shows_status.py```

Add the generated files into the Kometa config:

```
Anime:
    collection_files:
    - file: config/collections/anime-next-airing.yml
    overlay_files:
    - file: config/overlays/anime_status_overlays.yml
```
