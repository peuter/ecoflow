from homie.device_base import Device_Base
from homie.node.node_base import Node_Base
import model.protos.options_pb2 as options
import logging
import re

from homie.node.property.property_integer import Property_Integer
from homie.node.property.property_float import Property_Float
from homie.node.property.property_boolean import Property_Boolean
from homie.node.property.property_enum import Property_Enum
from homie.node.property.property_string import Property_String
from model.utils.event_emitter import EventEmitter

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class Proto_Device(Device_Base, EventEmitter):
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
        EventEmitter.__init__(self)
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
                    args = [node]
                    id = self.get_id(mapping_options.id, descriptor.name)
                    kwargs = {
                        "id": id,
                        "name": mapping_options.display_name if mapping_options.display_name != "" else descriptor.name,
                        "unit": mapping_options.unit,
                        "settable": False
                    }                    
                    if mapping_options.HasField("settable") and mapping_options.settable is True:
                        kwargs["settable"] = True
                        _LOGGER.debug(f"adding set event for {id}")
                        kwargs["set_value"] = (lambda v, name=id, event="set_request": self._set_value(event, name, v))

                    if descriptor.type == descriptor.TYPE_BOOL:                        
                        property = Property_Boolean(*args, **kwargs)
                    elif descriptor.type in [descriptor.TYPE_UINT32, descriptor.TYPE_INT32, descriptor.TYPE_SINT32, descriptor.TYPE_FIXED32, descriptor.TYPE_SFIXED32]:
                        if mapping_options.divisor > 1:
                            # must be a float
                            property = Property_Float(*args, **kwargs)
                        else:
                            # integer
                            property = Property_Integer(*args, **kwargs)
                    elif descriptor.type in [descriptor.TYPE_UINT64, descriptor.TYPE_INT64, descriptor.TYPE_SINT64, descriptor.TYPE_FIXED64, descriptor.TYPE_SFIXED64]:
                        _LOGGER.error(f"64bit integers are not supported by homie. skipping field {descriptor.name}")
                    elif descriptor.type == descriptor.TYPE_ENUM:
                        kwargs["data_format"] = ",".join(descriptor.enum_type.values_by_name.keys())
                        property = Property_Enum(*args, **kwargs)
                    elif descriptor.type == descriptor.TYPE_FLOAT:
                        property = Property_Float(*args, **kwargs)
                    elif descriptor.type == descriptor.TYPE_STRING:
                        property = Property_String(*args, **kwargs)


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

    def _set_value(self, event, id, value):
        _LOGGER.debug(f"{event} setter for {id} has been called with value '{value}'")
        self.emit(event, id, value)

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
    
    def bind(self, func, as_name=None):
        """
        Bind the function *func* to *instance*, with either provided name *as_name*
        or the existing name of *func*. The provided *func* should accept the 
        instance as the first argument, i.e. "self".
        """
        if as_name is None:
            as_name = func.__name__
        bound_method = func.__get__(self, self.__class__)
        setattr(self, as_name, bound_method)
        return bound_method

