import logging
import os
import json
import paho.mqtt.client as mqtt
from settings import *

class MQTTPublisher:

    def __init__(self):
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USER", "")
        self.password = os.getenv("MQTT_PASSWORD", "")
        self.topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", DEFAULT_MQTT_PREFIX)
        
        self.client = mqtt.Client()
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            logging.info(f"Connected to MQTT Broker: {self.broker}:{self.port}")
        except Exception as e:
            logging.error(f"Failed to connect to MQTT Broker: {e}")

    def publish_user_data(self, user_id: str, balance: float, last_daily_date: str, last_daily_usage: float, yearly_charge: float, yearly_usage: float, month_charge: float, month_usage: float):
        if balance is not None:
            self.publish_sensor(user_id, "balance", balance, UNIT_MONEY, "mdi:cash", "monetary", "total")
            
        if last_daily_usage is not None:
            self.publish_sensor(user_id, "last_daily_usage", last_daily_usage, UNIT_ENERGY, "mdi:lightning-bolt", "energy", "measurement", {"last_reset": last_daily_date})
            
        if yearly_usage is not None:
            self.publish_sensor(user_id, "yearly_usage", yearly_usage, UNIT_ENERGY, "mdi:lightning-bolt", "energy", "total_increasing")
            
        if yearly_charge is not None:
            self.publish_sensor(user_id, "yearly_charge", yearly_charge, UNIT_MONEY, "mdi:cash", "monetary", "total_increasing")
            
        if month_usage is not None:
            self.publish_sensor(user_id, "month_usage", month_usage, UNIT_ENERGY, "mdi:lightning-bolt", "energy", "measurement")
            
        if month_charge is not None:
            self.publish_sensor(user_id, "month_charge", month_charge, UNIT_MONEY, "mdi:cash", "monetary", "measurement")

        logging.info(f"User {user_id} data published to MQTT successfully!")

    def publish_sensor(self, user_id, sensor_type, value, unit, icon, device_class, state_class, extra_attrs=None):
        """
        Publish sensor data to MQTT and send Auto Discovery config
        """
        sensor_name = f"{sensor_type}_{user_id[-4:]}"
        unique_id = f"sgcc_{user_id}_{sensor_type}"
        state_topic = f"{self.topic_prefix}/{user_id}/{sensor_type}/state"
        config_topic = f"{DEFAULT_DISCOVERY_PREFIX}/{DEFAULT_COMPONENT}/sgcc_{user_id}/{sensor_type}/config"
        
        # 1. Publish Auto Discovery Config (Retained)
        config_payload = {
            "name": f"SGCC {user_id} {sensor_type.replace('_', ' ').title()}",
            "unique_id": unique_id,
            "state_topic": state_topic,
            "unit_of_measurement": unit,
            "icon": icon,
            "device_class": device_class,
            "state_class": state_class,
            "platform": "mqtt",
            "device": {
                "identifiers": [f"sgcc_{user_id}"],
                "name": f"95598 AccountNo. {user_id}",
                "manufacturer": "State Grid Corporation of China",
                "model": "Electricity Monitor",
                "sw_version": "1.0"
            }
        }
        self.client.publish(config_topic, json.dumps(config_payload), retain=True)
        
        # 2. Publish State
        self.client.publish(state_topic, str(value), retain=True)
        
        logging.info(f"Published {sensor_name}: {value} {unit}")
