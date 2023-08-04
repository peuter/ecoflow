from homie.device_base import Device_Base
from homie.node.node_base import Node_Base
import model.protos.options_pb2 as options

import logging
import re

from homie.node.property.property_integer import Property_Integer
from homie.node.property.property_float import Property_Float

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class Proto_Device(Device_Base):
    def __init__(
        self,
        proto_message,
        device_id=None,
        name=None,
        homie_settings=None,
        mqtt_settings=None,
        temp_unit="C"        
    ):
        super().__init__(device_id, name, homie_settings, mqtt_settings)
        self.temp_unit = temp_unit

        # init nodes from message options
        for homie_node in proto_message.DESCRIPTOR.GetOptions().Extensions[options.homie_node]:
            retain = True
            if hasattr(homie_node, "no_retain") and getattr(homie_node, "no_retain") is True:
                retain = False
            qos = 1
            if hasattr(homie_node, "qos") and getattr(homie_node, "qos") > 0:
                qos = getattr(homie_node, "qos") - 1
            node = Node_Base(self, getattr(homie_node, "id"), getattr(homie_node, "name"), getattr(homie_node, "type"), retain=retain, qos=qos)
            self.add_node(node)
            _LOGGER.debug(f"node {homie_node.id} has been added")

        # add properties to nodes
        for descriptor in proto_message.DESCRIPTOR.fields:
            mapping_options = descriptor.GetOptions().Extensions[options.mapping_options]
            if mapping_options.node != "":
                node = self.get_node(mapping_options.node)
                if node is not None:
                    if mapping_options.divisor > 1:
                        # must be a float
                        property = Property_Float(node,
                            id=self.get_id(mapping_options.id, descriptor.name),
                            name=mapping_options.display_name if mapping_options.display_name != "" else descriptor.name,
                            unit=mapping_options.unit,
                            settable=False
                            )
                    else:
                        # integer
                        property = Property_Integer(node,
                            id=self.get_id(mapping_options.id, descriptor.name),
                            name=mapping_options.display_name if mapping_options.display_name != "" else descriptor.name,
                            unit=mapping_options.unit,
                            settable=False
                            )
                    node.add_property(property)
                    _LOGGER.debug(f"property {property.name} has been added to node {node.name}")
                else:
                    _LOGGER.error(f"node {mapping_options.node} does not exists field {descriptor.name} will not be mapped to homie!")

        # add derived properties
        for derived_field in proto_message.DESCRIPTOR.GetOptions().Extensions[options.derived_field]:
            if derived_field.node != "":
                node = self.get_node(derived_field.node)
                if node is not None:
                    # must be a float
                    property = Property_Float(node,
                        id=self.get_id("", derived_field.field_name),
                        name=derived_field.display_name if derived_field.display_name != "" else derived_field.id,
                        unit=derived_field.unit,
                        settable=False
                        )
                    node.add_property(property)
                _LOGGER.debug(f"derived property {property.name} has been added to node {node.name}")
        self.start()

    def update(self, value, descriptor=None, node_name=None, id=None, name=None):
        mapping_options = descriptor.GetOptions().Extensions[options.mapping_options] if descriptor is not None else None
        node = None
        if node_name is not None:
            node = self.get_node(node_name)
        elif mapping_options is not None and mapping_options.node != "":
            node = self.get_node(mapping_options.node)
        if node is not None:
            property_name = None
            if id is not None or name is not None:
                property_name = self.get_id(id, name)
            elif mapping_options is not None:
                property_name = self.get_id(mapping_options.id, descriptor.name)
            if property_name is not None:
                node.get_property(property_name).value = value
                

    def get_id(self, id, name):
        if id != "" and id is not None:
            return id
        name = re.sub('[^0-9a-zA-Z]+', '-', name)
        # CamelCase to camel-case
        return re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()

