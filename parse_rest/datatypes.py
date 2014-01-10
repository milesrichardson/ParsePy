#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import base64
import datetime

from connection import API_ROOT, ParseBase
from query import QueryManager


class ParseType(object):

    @staticmethod
    def convert_from_parse(parse_data, class_name):

        is_parse_type = isinstance(parse_data, dict) and '__type' in parse_data

        # if its not a parse type -- simply return it. This means it wasn't a "special class"
        if not is_parse_type:

            return parse_data

        # determine just which kind of parse type this element is - ie: a built in parse type such as File, Pointer, User etc 
        parse_type = parse_data['__type']

        # if its a pointer, we need to handle to ensure that we don't mishandle a circular reference
        if parse_type == "Pointer":
            
            # grab the pointer object here
            return Pointer.from_native(class_name, **parse_data)

            # return a recursive handled Pointer method
            return True

        # now handle the other parse types accordingly
        native = {
            'Date': Date,
            'Bytes': Binary,
            'GeoPoint': GeoPoint,
            'File': File,
            'Relation': Relation
            }.get(parse_type)

        return native and native.from_native(**parse_data) or parse_data

    @staticmethod
    def convert_to_parse(python_object, as_pointer=False):
        is_object = isinstance(python_object, Object)

        if is_object and not as_pointer:
            return dict([(k, ParseType.convert_to_parse(v, as_pointer=True))
                         for k, v in python_object._editable_attrs.items()
                         ])

        python_type = Object if is_object else type(python_object)

        # classes that need to be cast to a different type before serialization
        transformation_map = {
            datetime.datetime: Date,
            Object: Pointer
            }

        if python_type in transformation_map:
            klass = transformation_map.get(python_type)
            return klass(python_object)._to_native()

        if isinstance(python_object, ParseType):
            return python_object._to_native()

        return python_object

    @classmethod
    def from_native(cls, **kw):
        return cls(**kw)

    def _to_native(self):
        return self._value


class Pointer(ParseType):
    
    @classmethod
    def from_native(cls, parent_class_name = None, **kw):
        
        # grab the object data manually here so we can manipulate it before passing back an actual object
        klass = Object.factory(kw.get('className'))
        objectData = klass.GET("/" + kw.get('objectId'))
        
        # now lets check if we have circular references here
        if parent_class_name:

            # now lets see if we have any references to the parent class here
            for key, value in objectData.iteritems():
                
                if type(value) == dict and "className" in value and value["className"] == parent_class_name:
                    
                    # simply put the reference here as a string  -- not sure what the drawbacks are for this but it works for me 
                    objectData[key] = value["objectId"] 
                
        # set a temporary flag that will remove the recursive pointer types etc
        klass = Object.factory(kw.get('className'))
        return klass(**objectData)

    def __init__(self, obj):

        self._object = obj

    def _to_native(self):
        return {
            '__type': 'Pointer',
            'className': self._object.__class__.__name__,
            'objectId': self._object.objectId
            }


class Relation(ParseType):
    @classmethod
    def from_native(cls, **kw):
        pass


class Date(ParseType):
    FORMAT = '%Y-%m-%dT%H:%M:%S.%f%Z'

    @classmethod
    def from_native(cls, **kw):
        return cls._from_str(kw.get('iso', ''))

    @staticmethod
    def _from_str(date_str):
        """turn a ISO 8601 string into a datetime object"""
        return datetime.datetime.strptime(date_str[:-1] + 'UTC', Date.FORMAT)

    def __init__(self, date):
        """Can be initialized either with a string or a datetime"""
        if isinstance(date, datetime.datetime):
            self._date = date
        elif isinstance(date, unicode):
            self._date = Date._from_str(date)

    def _to_native(self):
        return {
            '__type': 'Date', 'iso': self._date.isoformat()
            }


class Binary(ParseType):

    @classmethod
    def from_native(cls, **kw):
        return cls(kw.get('base64', ''))

    def __init__(self, encoded_string):
        self._encoded = encoded_string
        self._decoded = str(base64.b64decode(self._encoded))

    def _to_native(self):
        return {'__type': 'Bytes', 'base64': self._encoded}


class GeoPoint(ParseType):

    @classmethod
    def from_native(cls, **kw):
        return cls(kw.get('latitude'), kw.get('longitude'))

    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

    def _to_native(self):
        return {
            '__type': 'GeoPoint',
            'latitude': self.latitude,
            'longitude': self.longitude
            }


class File(ParseType):

    @classmethod
    def from_native(cls, **kw):
        return cls(**kw)

    def __init__(self, **kw):
        name = kw.get('name')
        self._name = name
        self._api_url = '/'.join([API_ROOT, 'files', name])
        self._file_url = kw.get('url')

    def _to_native(self):
        return {
            '__type': 'File',
            'name': self._name
            }

    url = property(lambda self: self._file_url)
    name = property(lambda self: self._name)
    _absolute_url = property(lambda self: self._api_url)


class Function(ParseBase):
    ENDPOINT_ROOT = '/'.join((API_ROOT, 'functions'))

    def __init__(self, name):
        self.name = name

    def __call__(self, **kwargs):
        return self.POST('/' + self.name, **kwargs)


class ParseResource(ParseBase, Pointer):

    PROTECTED_ATTRIBUTES = ['objectId', 'createdAt', 'updatedAt']

    @classmethod
    def retrieve(cls, resource_id):
        return cls(**cls.GET('/' + resource_id))

    @property
    def _editable_attrs(self):
        protected_attrs = self.__class__.PROTECTED_ATTRIBUTES
        allowed = lambda a: a not in protected_attrs and not a.startswith('_')
        return dict([(k, v) for k, v in self.__dict__.items() if allowed(k)])

    def __init__(self, **kw):

        for key, value in kw.items():
            setattr(self, key, ParseType.convert_from_parse(value, self.__class__.__name__))

    def _to_native(self):
        return ParseType.convert_to_parse(self)

    def _get_object_id(self):
        return self.__dict__.get('_object_id')

    def _set_object_id(self, value):
        if '_object_id' in self.__dict__:
            raise ValueError('Can not re-set object id')
        self._object_id = value

    def _get_updated_datetime(self):
        return self.__dict__.get('_updated_at') and self._updated_at._date

    def _set_updated_datetime(self, value):
        self._updated_at = Date(value)

    def _get_created_datetime(self):
        return self.__dict__.get('_created_at') and self._created_at._date

    def _set_created_datetime(self, value):
        self._created_at = Date(value)

    def save(self, batch=False):
        if self.objectId:
            return self._update(batch=batch)
        else:
            return self._create(batch=batch)

    def _create(self, batch=False):
        uri = self.__class__.ENDPOINT_ROOT
        response = self.__class__.POST(uri, batch=batch, **self._to_native())

        def call_back(response_dict):
            self.createdAt = self.updatedAt = response_dict['createdAt']
            self.objectId = response_dict['objectId']

        if batch:
            return response, call_back
        else:
            call_back(response)

    def _update(self, batch=False):
        response = self.__class__.PUT(self._absolute_url, batch=batch,
                                      **self._to_native())

        def call_back(response_dict):
            self.updatedAt = response_dict['updatedAt']

        if batch:
            return response, call_back
        else:
            call_back(response)

    def delete(self, batch=False):
        response = self.__class__.DELETE(self._absolute_url, batch=batch)
        def call_back(response_dict):
            self.__dict__ = {}

        if batch:
            return response, call_back
        else:
            call_back(response)

    _absolute_url = property(
        lambda self: '/'.join([self.__class__.ENDPOINT_ROOT, self.objectId])
        )

    objectId = property(_get_object_id, _set_object_id)
    createdAt = property(_get_created_datetime, _set_created_datetime)
    updatedAt = property(_get_updated_datetime, _set_updated_datetime)

    def __repr__(self):
        return '<%s:%s>' % (unicode(self.__class__.__name__), self.objectId)


class ObjectMetaclass(type):
    def __new__(cls, name, bases, dct):
        cls = super(ObjectMetaclass, cls).__new__(cls, name, bases, dct)
        cls.set_endpoint_root()
        cls.Query = QueryManager(cls)
        return cls


class Object(ParseResource):
    __metaclass__ = ObjectMetaclass
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'classes'])

    @classmethod
    def factory(cls, class_name):

        class DerivedClass(cls):
            pass
        DerivedClass.__name__ = str(class_name)
        DerivedClass.set_endpoint_root()
        return DerivedClass

    @classmethod
    def set_endpoint_root(cls):
        root = '/'.join([API_ROOT, 'classes', cls.__name__])
        if cls.ENDPOINT_ROOT != root:
            cls.ENDPOINT_ROOT = root
        return cls.ENDPOINT_ROOT

    @property
    def _absolute_url(self):
        if not self.objectId: return None
        return '/'.join([self.__class__.ENDPOINT_ROOT, self.objectId])

    @property
    def as_pointer(self):
        return Pointer(**{
                'className': self.__class__.__name__,
                'objectId': self.objectId
                })

    def increment(self, key, amount=1):
        """
        Increment one value in the object. Note that this happens immediately:
        it does not wait for save() to be called
        """
        payload = {
            key: {
                '__op': 'Increment',
                'amount': amount
                }
            }
        self.__class__.PUT(self._absolute_url, **payload)
        self.__dict__[key] += amount
