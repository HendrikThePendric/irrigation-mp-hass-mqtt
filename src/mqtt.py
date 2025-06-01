from umqtt.simple import MQTTClient
import ssl


def mqtt_connect():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(cafile="./ca_crt.der")
    ssl_context.load_cert_chain(
        certfile="./irrigationbackyard_crt.der", keyfile="./irrigationbackyard_key.der"
    )
    client = MQTTClient(
        client_id="test_id",
        server="192.168.68.99",
        port=8883,
        keepalive=60,
        ssl=ssl_context,
    )
    client.connect()
    print("Connected to MQTT Broker")
    return client
