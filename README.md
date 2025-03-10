Script will generate collection and overlay files for Kometa. Collection is used for next airing status ordered by date. 

Existing statuses:

| Status Name            | Hex Code   | Color Name       | Description                                                                 |
|------------------------|------------|------------------|-----------------------------------------------------------------------------|
| `AIRING`               | `#006580`  | Dark Cyan        | Currently airing shows with next episode date                              |
| `ENDED`                | `#000000`  | Black            | Ended series                                                               |
| `CANCELLED`            | `#FF0000`  | Red              | Cancelled shows                                                            |
| `RETURNING`            | `#008000`  | Green            | Returning series waiting for next episode                                 |
| `SEASON FINALE`        | `#9932CC`  | Dark Orchid      | Season finale episodes with airing date                                                   |
| `MID SEASON FINALE`    | `#FFA500`  | Orange           | Mid-season finale episodes with airing date                                                |
| `FINAL EPISODE`        | `#8B0000`  | Dark Red         | Final episode of a series with airing date                                                |
| `SEASON PREMIERE`      | `#228B22`  | Forest Green     | Season premiere episodes with airing date                                                  |

You can change the colors to your liking. 

# Collection on Home
<img src="https://zipline.rlvd.eu/u/eKH4fr.png">

# Some status examples
<img src="https://zipline.rlvd.eu/u/WHsD5C.png" width="415">&nbsp;
<img src="https://zipline.rlvd.eu/u/zIbynV.png" width="200">&nbsp;
<img src="https://zipline.rlvd.eu/u/4bY6B9.png" width="415">&nbsp;
<img src="https://zipline.rlvd.eu/u/ZcWejl.png" width="200">

# Usage

Generate a trakt application.

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
