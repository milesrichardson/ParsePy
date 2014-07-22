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
from __future__ import unicode_literals

import base64
import datetime
import six

from parse_rest.connection import API_ROOT, ParseBase
from parse_rest.query import QueryManager


def complex_type(name=None):
    '''Decorator for registering complex types'''
    def wrapped(cls):
        ParseType.type_mapping[name or cls.__name__] = cls
        return cls
    return wrapped


class ParseType(object):
    type_mapping = {}

    @staticmethod
    def convert_from_parse(parse_data):

        is_parse_type = isinstance(parse_data, dict) and '__type' in parse_data

        # if its not a parse type -- simply return it. This means it wasn't a "special class"
        if not is_parse_type:
            return parse_data

        native = ParseType.type_mapping.get(parse_data.pop('__type'))
        return  native.from_native(**parse_data) if native else parse_data

    @staticmethod
    def convert_to_parse(python_object, as_pointer=False):
        is_object = isinstance(python_object, ParseResource) #User is derived from ParseResouce not Object, check against ParseResource

        if is_object and not as_pointer:
            return dict([(k, ParseType.convert_to_parse(v, as_pointer=True))
                         for k, v in python_object._editable_attrs.items()
                         ])

        python_type = ParseResource if is_object else type(python_object)

        # classes that need to be cast to a different type before serialization
        transformation_map = {
            datetime.datetime: Date,
            ParseResource: Pointer
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
        raise NotImplementedError("_to_native must be overridden")


@complex_type('Pointer')
class Pointer(ParseType):

    @classmethod
    def from_native(cls, **kw):
        # create object with only objectId and unloaded flag. it is automatically loaded when any other field is accessed
        klass = Object.factory(kw.get('className'))
        return klass(objectId=kw.get('objectId'), _is_loaded=False)


    def __init__(self, obj):
        self._object = obj

    def _to_native(self):
        return {
            '__type': 'Pointer',
            'className': self._object.className,
            'objectId': self._object.objectId
        }


@complex_type('Object')
class EmbeddedObject(ParseType):
    @classmethod
    def from_native(cls, **kw):
        klass = Object.factory(kw.pop('className'))
        return klass(**kw)


@complex_type()
class Relation(ParseType):
    @classmethod
    def from_native(cls, **kw):
        pass


@complex_type()
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
        elif isinstance(date, six.string_types):
            self._date = Date._from_str(date)

    def _to_native(self):
        return {  #parse expects an iso8601 with 3 digits milliseonds and not 6
            '__type': 'Date', 'iso': '{0}Z'.format(self._date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3])
            }


@complex_type('Bytes')
class Binary(ParseType):

    @classmethod
    def from_native(cls, **kw):
        return cls(kw.get('base64', ''))

    def __init__(self, encoded_string):
        self._encoded = encoded_string
        self._decoded = str(base64.b64decode(self._encoded))

    def _to_native(self):
        return {'__type': 'Bytes', 'base64': self._encoded}


@complex_type()
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


@complex_type()
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
            'name': self._name,
            'url': self._file_url
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


class ParseResource(ParseBase):

    PROTECTED_ATTRIBUTES = ['objectId', 'createdAt', 'updatedAt']

    @property
    def _editable_attrs(self):
        protected_attrs = self.__class__.PROTECTED_ATTRIBUTES
        allowed = lambda a: a not in protected_attrs and not a.startswith('_')
        return dict([(k, v) for k, v in self.__dict__.items() if allowed(k)])

    def __init__(self, **kw):
        self.objectId = None
        self._init_attrs(kw)

    def __getattr__(self, attr):
        # if object is not loaded and attribute is missing, try to load it
        if not self.__dict__.get('_is_loaded', True):
            del self._is_loaded
            self._init_attrs(self.GET(self._absolute_url))
        return object.__getattribute__(self, attr) #preserve default if attr not exists

    def _init_attrs(self, args):
        for key, value in six.iteritems(args):
            setattr(self, key, ParseType.convert_from_parse(value))

    def _to_native(self):
        return ParseType.convert_to_parse(self)


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
        response = self.__class__.PUT(self._absolute_url, batch=batch, **self._to_native())

        def call_back(response_dict):
            self.updatedAt = response_dict['updatedAt']

        if batch:
            return response, call_back
        else:
            call_back(response)

    def delete(self, batch=False):
        response = self.__class__.DELETE(self._absolute_url, batch=batch)
        if batch:
            return response, lambda response_dict: None

    @property
    def className(self):
        return self.__class__.__name__

    @property
    def _absolute_url(self):
        return '%s/%s' % (self.__class__.ENDPOINT_ROOT, self.objectId)

    createdAt = property(_get_created_datetime, _set_created_datetime)
    updatedAt = property(_get_updated_datetime, _set_updated_datetime)

    def __repr__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.objectId)


class ObjectMetaclass(type):
    def __new__(mcs, name, bases, dct):
        cls = super(ObjectMetaclass, mcs).__new__(mcs, name, bases, dct)
        # attr check must be here because of specific six.with_metaclass implemetantion where metaclass is used also for
        # internal NewBase which hasn't set_endpoint_root method
        if hasattr(cls, 'set_endpoint_root'):
            cls.set_endpoint_root()
            cls.Query = QueryManager(cls)
        return cls


class Object(six.with_metaclass(ObjectMetaclass, ParseResource)):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'classes'])

    @classmethod
    def factory(cls, class_name):
        """find proper Object subclass matching class_name
        system types like _User are mapped to types without underscore (parse_resr.user.User)
        If user don't declare matching type, class is created on the fly
        """
        class_name = str(class_name.lstrip('_'))
        types = ParseResource.__subclasses__()
        while types:
            t = types.pop()
            if t.__name__ == class_name:
                return t
            types.extend(t.__subclasses__())
        else:
            return type(class_name, (Object,), {})

    @classmethod
    def set_endpoint_root(cls):
        root = '/'.join([API_ROOT, 'classes', cls.__name__])
        if cls.ENDPOINT_ROOT != root:
            cls.ENDPOINT_ROOT = root
        return cls.ENDPOINT_ROOT

    @property
    def _absolute_url(self):
        if not self.objectId:
            return None
        return '/'.join([self.__class__.ENDPOINT_ROOT, self.objectId])

    @property
    def as_pointer(self):
        return Pointer(self)

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

    def removeRelation(self, key, className, objectsId):
        self.manageRelation('RemoveRelation', key, className, objectsId)

    def addRelation(self, key, className, objectsId):
        self.manageRelation('AddRelation', key, className, objectsId)

    def manageRelation(self, action, key, className, objectsId):
        objects = [{
                    "__type": "Pointer",
                    "className": className,
                    "objectId": objectId
                    } for objectId in objectsId]

        payload = {
            key: {
                 "__op": action,
                 "objects": objects
                }
            }
        self.__class__.PUT(self._absolute_url, **payload)
        self.__dict__[key] = ''
