from django.core import serializers
from utils.json_encoder import JSONEncoder


class DjangoModelSerializer:

    @classmethod
    def serialize(cls, instance):
        # Django serializers take Queryset or list as input data type
        # Thus need to add [] to convert instance to list
        return serializers.serialize('json', [instance], cls=JSONEncoder)

    @classmethod
    def deserialize(cls, serialized_data):
        # need .object to get the original model type of object,
        # otherwise get DeserializedObject type, instead of ORM model
        return list(serializers.deserialize('json', serialized_data))[0].object