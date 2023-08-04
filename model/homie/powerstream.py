from homie.device_base import Device_Base
from homie.node.node_base import Node_Base

from homie.node.property.property_integer import Property_Integer
from homie.node.property.property_battery import Property_Battery
from homie.node.property.property_temperature import Property_Temperature


class Device_Powerstream(Device_Base):
    def __init__(
        self,
        device_id=None,
        name=None,
        homie_settings=None,
        mqtt_settings=None,
        temp_unit="C"
    ):
        super().__init__(device_id, name, homie_settings, mqtt_settings)
        self.temp_unit = temp_unit

        # node = Node_Base(self, "controls", "Controls", "controls")
        # self.add_node(node)

        self.register_properties()
       
        self.start()

    def register_status_properties(self, node):
        
        node = Node_Base(self, "pv1", "PV1", "pv1")
        self.add_node(node)       
        self.pv1_input_watts = Property_Integer(node, unit="W", id="pv1-input-watts", name="PV1 input", settable=False)
        node.add_property(self.pv1_input_watts)
        self.pv1_temperature = Property_Temperature(node, unit=self.temp_unit, id="pv1-temp", name="PV1 temperature")
        node.add_property(self.pv1_temperature)

        node = Node_Base(self, "pv2", "PV2", "pv2")
        self.add_node(node)
        self.pv2_input_watts = Property_Integer(node, unit="W", id="pv2-input-watts", name="PV2 input", settable=False)
        node.add_property(self.pv2_input_watts)
        self.pv2_temperature = Property_Temperature(node, unit=self.temp_unit, id="pv2-temp", name="PV2 temperature")
        node.add_property(self.pv2_temperature)

        node = Node_Base(self, "battery", "Battery", "battery")
        self.soc = Property_Battery(node)
        node.add_property(self.soc)
        self.battery_temperature = Property_Temperature(node, unit=self.temp_unit, id="battery-temp", name="Battery temperature")
        node.add_property(self.battery_temperature)

        node = Node_Base(self, "states", "States", "states")
        self.pv_input_watts = Property_Integer(node, unit="W", id="pv-input-watts", name="PV total", settable=False)
        node.add_property(self.pv_input_watts)
        self.permanent_watts = Property_Integer(node, unit="W", id="permanent-watts", name="Permanent watts", settable=False)
        node.add_property(self.permanent_watts)
        self.dynamic_watts = Property_Integer(node, unit="W", id="dynamic-watts", name="Dynamic watts", settable=False)
        node.add_property(self.dynamic_watts)
        self.inverter_output_watts = Property_Integer(node, unit="W", id="inverter-output-watts", name="Inverter output", settable=False)
        node.add_property(self.inverter_output_watts)        


    def update_pv1_input_watts(self, value):
        self.pv1_input_watts.value = value
    
    def update_pv2_input_watts(self, value):
        self.pv2_input_watts.value = value

    def update_pv_input_watts(self, value):
        self.pv_input_watts.value = value

    def update_permanent_watts(self, value):
        self.permanent_watts.value = value

    def update_dynamic_watts(self, value):
        self.dynamic_watts.value = value

    def update_dynamic_watts(self, value):
        self.dynamic_watts.value = value        

    def update_pv1_temperature(self, value):
        self.pv1_temperature.value = value                

    def update_pv2_temperature(self, value):
        self.pv2_temperature.value = value  

    def update_battery_temperature(self, value):
        self.battery_temperature.value = value          

    def update_inverter_output_watts(self, value):
        self.inverter_output_watts.value = value            

    def update_soc(self, soc):
        self.soc.value = soc