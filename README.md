# ecoflow MQTT client

Connect to ecoflow MQTT server to communicate with an ecoflow device (currently only powerstream microinverters, smartplugs and delta max are supported). Creates a [homie](https://homieiot.github.io/) device for the ecoflow devices to be able to integrate them into smarthome systems with homie support.

## start

1. Create virtual environment and install dependencies
```shell
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

2. Create `.env` file with credentials to login
```dotenv
EF_USERNAME="ecoflow account username (email address)"
EF_PASSWORD="ecoflow account password"
```
3. Create `config.json`
```json
{
    "devices": [{
        "type": "powerstream",
        "serial": "serial-number of the powerstream device"
    }]
}
```

4. Run: `./index.py`
