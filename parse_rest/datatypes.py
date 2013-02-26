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
import urllib2

from __init__ import ParseBase, API_ROOT
from query import QueryManager

class ParseType(object):

    @staticmethod
    def convert_from_parse(parse_data):
        is_parse_type = isinstance(parse_data, dict) and '__type' in parse_data
        if not is_parse_type:
            return parse_data

        parse_type = parse_data['__type']
        native = {
            'Pointer': Pointer,
            'Date': Date,
            'Bytes': Binary,
            'GeoPoint': GeoPoint,
            'File': File,
            'Relation': Relation
            }.get(parse_type)

        return native and native.from_native(**parse_data) or parse_data

    @staticmethod
    def convert_to_parse(python_object):
        if isinstance(python_object, ParseType):
            return python_object._to_native()

        # This seems rather pointless now that we are only working
        # with dates. Perhaps when files/images start to get a little
        # more attention, we will have more things here.
        python_type = type(python_object)
        klass = {
            datetime.datetime: Date
            }.get(python_type)

        return klass(python_object)._to_native() if klass else python_object

    @classmethod
    def from_native(cls, **kw):
        return cls(**kw)

    def _to_native(self):
        return self._value


class Pointer(ParseType):

    @classmethod
    def from_native(cls, **kw):
        klass = Object.factory(kw.get('className'))
        return klass.retrieve(kw.get('objectId'))

    def _to_native(self):
        return {
            '__type': 'Pointer',
            'className': self.__class__.__name__,
            'objectId': self.objectId
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
        return cls(kw.get('url'), kw.get('name'))

    def __init__(self, url, name):
        request = urllib2.Request(url)
        self._name = name
        self._url = url
        self._file = urllib2.urlopen(request)

    def _to_native(self):
        return {
            '__type': 'File',
            'name': self._name
            }


class ParseResource(ParseBase, Pointer):

    PROTECTED_ATTRIBUTES = ['objectId', 'createdAt', 'updatedAt']

    @classmethod
    def retrieve(cls, resource_id):
        return cls(**cls.GET('/' + resource_id))

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, ParseType.convert_from_parse(value))

    def _to_dict(self):
        # serializes all attributes that need to be persisted on Parse

        protected_attributes = self.__class__.PROTECTED_ATTRIBUTES
        is_protected = lambda a: a in protected_attributes or a.startswith('_')


        return dict([(k, ParseType.convert_to_parse(v))
                     for k, v in self.__dict__.items() if not is_protected(k)
                     ])

    def _get_object_id(self):
        return getattr(self, '_object_id', None)

    def _set_object_id(self, value):
        if hasattr(self, '_object_id'):
            raise ValueError('Can not re-set object id')
        self._object_id = value

    def _get_updated_datetime(self):
        return getattr(self, '_updated_at', None) and self._updated_at._date

    def _set_updated_datetime(self, value):
        self._updated_at = Date(value)

    def _get_created_datetime(self):
        return getattr(self, '_created_at', None) and self._created_at._date

    def _set_created_datetime(self, value):
        self._created_at = Date(value)

    def save(self):
        if self.objectId:
            self._update()
        else:
            self._create()

    def _create(self):
        # URL: /1/classes/<className>
        # HTTP Verb: POST

        uri = self.__class__.ENDPOINT_ROOT

        response_dict = self.__class__.POST(uri, **self._to_dict())

        self.createdAt = self.updatedAt = response_dict['createdAt']
        self.objectId = response_dict['objectId']

    def _update(self):
        # URL: /1/classes/<className>/<objectId>
        # HTTP Verb: PUT

        response = self.__class__.PUT(self._absolute_url, **self._to_dict())
        self.updatedAt = response['updatedAt']

    def delete(self):
        self.__class__.DELETE(self._absolute_url)
        self.__dict__ = {}

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
        if not self.objectId:
            return None

        return '/'.join([self.__class__.ENDPOINT_ROOT, self.objectId])

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

