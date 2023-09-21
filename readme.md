# Mydealzbot

## Setup

```
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
```

* config.ini aus config.ini.example erstellen
* leere Datei mydealz.sqlite erstellen
* `docker compose up -d`
* cronjob einrichten (dieser Teil ist leider nicht in Docker): 
```
*/5 * * * * cd /path/zum/bot && bin/python3 mydealz.py > /dev/null
```
