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

import urllib
import urllib2
import base64
import json
import datetime
import collections
import re
import logging

API_ROOT = 'https://api.parse.com/1'

APPLICATION_ID = ''
REST_API_KEY = ''


class ParseBinaryDataWrapper(str):
    pass


class ParseBase(object):
    ENDPOINT_ROOT = API_ROOT

    @classmethod
    def execute(cls, uri, http_verb, extra_headers=None, **kw):
        headers = extra_headers or {}
        url = uri if uri.startswith(API_ROOT) else cls.ENDPOINT_ROOT + uri
        data = kw and json.dumps(kw) or "{}"
        if http_verb == 'GET' and data:
            url += '?%s' % urllib.urlencode(kw)
            data = None

        request = urllib2.Request(url, data)
        request.add_header('Content-type', 'application/json')
        #auth_header =  "Basic %s" % base64.b64encode('%s:%s' %
        #                            (APPLICATION_ID, REST_API_KEY))
        #request.add_header("Authorization", auth_header)
        request.add_header("X-Parse-Application-Id", APPLICATION_ID)
        request.add_header("X-Parse-REST-API-Key", REST_API_KEY)

        request.get_method = lambda: http_verb

        # TODO: add error handling for server response
        response = urllib2.urlopen(request)
        return json.loads(response.read())

    @classmethod
    def GET(cls, uri, **kw):
        return cls.execute(uri, 'GET', **kw)

    @classmethod
    def POST(cls, uri, **kw):
        return cls.execute(uri, 'POST', **kw)

    @classmethod
    def PUT(cls, uri, **kw):
        return cls.execute(uri, 'PUT', **kw)

    @classmethod
    def DELETE(cls, uri, **kw):
        return cls.execute(uri, 'DELETE', **kw)

    @property
    def _attributes(self):
        # return "public" attributes converted to the base parse representation
        return dict([
                self._convertToParseType(p) for p in self.__dict__.items()
                if p[0][0] != '_'
                ])

    def _isGeoPoint(self, value):
        if isinstance(value, str):
            return re.search('\\bPOINT\\(([-+]?[0-9]*\\.?[0-9]*) ' +
                             '([-+]?[0-9]*\\.?[0-9]*)\\)', value, re.I)

    def _ISO8601ToDatetime(self, date_string):
        # TODO: verify correct handling of timezone
        date_string = date_string[:-1] + 'UTC'
        return datetime.datetime.strptime(date_string,
                                            '%Y-%m-%dT%H:%M:%S.%f%Z')

    def _convertToParseType(self, prop):
        key, value = prop

        if type(value) == Object:
            value = {'__type': 'Pointer',
                    'className': value._class_name,
                    'objectId': value._object_id}
        elif type(value) == datetime.datetime:
            # take off the last 3 digits and add a Z
            value = {'__type': 'Date', 'iso': value.isoformat()[:-3] + 'Z'}
        elif type(value) == ParseBinaryDataWrapper:
            value = {'__type': 'Bytes',
                    'base64': base64.b64encode(value)}
        elif self._isGeoPoint(value):
            coordinates = re.findall('[-+]?[0-9]+\\.?[0-9]*', value)
            value = {'__type': 'GeoPoint',
                     'longitude': float(coordinates[0]),
                     'latitude': float(coordinates[1])}

        return (key, value)


class Function(ParseBase):
    ENDPOINT_ROOT = "/".join((API_ROOT, "functions"))

    def __init__(self, name):
        self.name = name

    def __call__(self, **kwargs):
        return self.POST("/" + self.name, **kwargs)


class ParseResource(ParseBase):
    def __init__(self, **kw):
        self._object_id = kw.pop('objectId', None)
        self._updated_at = kw.pop('updatedAt', None)
        self._created_at = kw.pop('createdAt', None)

        for attr, value in kw.items():
            self.__dict__[attr] = value

    @classmethod
    def retrieve(cls, resource_id):
        return cls(**cls.GET('/' + resource_id))

    _absolute_url = property(lambda self: '/'.join(
                             [self.__class__.ENDPOINT_ROOT, self._object_id]))

    def objectId(self):
        return self._object_id

    def updatedAt(self):
        return (self._updated_at and self._ISO8601ToDatetime(self._updated_at)
                    or None)

    def createdAt(self):
        return (self._created_at and self._ISO8601ToDatetime(self._created_at)
                    or None)


class User(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'users'])

    @classmethod
    def signup(cls, username, password, **kw):
        return cls.POST('', username=username, password=password, **kw)

    @classmethod
    def login(cls, username, password):
        return cls.GET('/'.join([API_ROOT, 'login']), username=username,
                            password=password)

    @classmethod
    def request_password_reset(cls, email):
        return cls.POST('/'.join([API_ROOT, 'requestPasswordReset']),
                         email=email)

    def save(self, session=None):
        session_header = {'X-Parse-Session-Token': session and
                                                 session.get('sessionToken')}

        return self.__class__.PUT(
                            self._absolute_url, extra_headers=session_header,
                            **self._attributes)


class Installation(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'installations'])


class Object(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'classes'])

    def __init__(self, class_name, attrs_dict=None):
        self._class_name = class_name
        self._object_id = None
        self._updated_at = None
        self._created_at = None

        if attrs_dict:
            self._populateFromDict(attrs_dict)

    def save(self):
        if self._object_id:
            self._update()
        else:
            self._create()

    def delete(self):
        # URL: /1/classes/<className>/<objectId>
        # HTTP Verb: DELETE

        self.__class__.DELETE('/%s/%s' % (self._class_name, self._object_id))
        self = self.__init__(None)

    def increment(self, key, amount=1):
        """
        Increment one value in the object. Note that this happens immediately:
        it does not wait for save() to be called
        """
        uri = '/%s/%s' % (self._class_name, self._object_id)
        payload = {
            key: {
                '__op': 'Increment',
                'amount': amount
                }
            }
        self._populateFromDict(self.__class__.execute(uri, 'PUT', **payload))

    def has(self, attr):
        return attr in self.__dict__

    def remove(self, attr):
        self.__dict__.pop(attr)

    def refresh(self):
        uri = '/%s/%s' % (self._class_name, self._object_id)
        response_dict = self.__class__.execute(uri, 'GET')
        self._populateFromDict(response_dict)

    def _populateFromDict(self, attrs_dict):
        if 'objectId' in attrs_dict:
            self._object_id = attrs_dict['objectId']
            del attrs_dict['objectId']
        if 'createdAt' in attrs_dict:
            self._created_at = attrs_dict['createdAt']
            del attrs_dict['createdAt']
        if 'updatedAt' in attrs_dict:
            self._updated_at = attrs_dict['updatedAt']
            del attrs_dict['updatedAt']

        attrs_dict = dict(map(self._convertFromParseType, attrs_dict.items()))

        self.__dict__.update(attrs_dict)

    def _convertFromParseType(self, prop):
        key, value = prop

        if type(value) == dict and '__type' in value:
            if value['__type'] == 'Pointer':
                value = ObjectQuery(value['className']).get(value['objectId'])
            elif value['__type'] == 'Date':
                value = self._ISO8601ToDatetime(value['iso'])
            elif value['__type'] == 'Bytes':
                value = ParseBinaryDataWrapper(base64.b64decode(
                                                            value['base64']))
            elif value['__type'] == 'GeoPoint':
                value = 'POINT(%s %s)' % (value['longitude'],
                                          value['latitude'])
            else:
                raise Exception('Invalid __type.')

        return (key, value)

    def _create(self):
        # URL: /1/classes/<className>
        # HTTP Verb: POST

        uri = '/%s' % self._class_name

        response_dict = self.__class__.POST(uri, **self._attributes)

        self._created_at = self._updated_at = response_dict['createdAt']
        self._object_id = response_dict['objectId']

    def _update(self):
        # URL: /1/classes/<className>/<objectId>
        # HTTP Verb: PUT

        uri = '/%s/%s' % (self._class_name, self._object_id)

        response_dict = self.__class__.PUT(uri, **self._attributes)
        self._updated_at = response_dict['updatedAt']


class Push(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'push'])

    @classmethod
    def send(cls, message, channels=None, **kw):
        alert_message = {'alert': message}
        targets = {}
        if channels:
            targets['channels'] = channels
        if kw:
            targets['where'] = kw
        return cls.POST('', data=alert_message, **targets)


class Query(ParseBase):

    def __init__(self):
        self._where = collections.defaultdict(dict)
        self._options = {}

    def eq(self, name, value):
        self._where[name] = value
        return self

    # It's tempting to generate the comparison functions programatically,
    # but probably not worth the decrease in readability of the code.
    def lt(self, name, value):
        self._where[name]['$lt'] = value
        return self

    def lte(self, name, value):
        self._where[name]['$lte'] = value
        return self

    def gt(self, name, value):
        self._where[name]['$gt'] = value
        return self

    def gte(self, name, value):
        self._where[name]['$gte'] = value
        return self

    def ne(self, name, value):
        self._where[name]['$ne'] = value
        return self

    def order(self, order, decending=False):
        # add a minus sign before the order value if decending == True
        self._options['order'] = decending and ('-' + order) or order
        return self

    def limit(self, limit):
        self._options['limit'] = limit
        return self

    def skip(self, skip):
        self._options['skip'] = skip
        return self

    def get(self, object_id):
        return self.__class__.QUERY_CLASS.retrieve(object_id)

    def fetch(self):
        # hide the single_result param of the _fetch method from the library
        # user since it's only useful internally
        return self._fetch()

    def _fetch(self):
        options = dict(self._options)  # make a local copy
        if self._where:
            # JSON encode WHERE values
            where = json.dumps(self._where)
            options.update({'where': where})

        response = self.__class__.GET('', **options)
        return [self.__class__.QUERY_CLASS(**result)
                    for result in response['results']]


class ObjectQuery(Query):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'classes'])

    def __init__(self, class_name):
        self._class_name = class_name
        self._where = collections.defaultdict(dict)
        self._options = {}
        self._object_id = ''

    def get(self, object_id):
        self._object_id = object_id
        return self._fetch(single_result=True)

    def _fetch(self, single_result=False):
        # URL: /1/classes/<className>/<objectId>
        # HTTP Verb: GET

        if self._object_id:
            response = self.__class__.GET('/%s/%s' % (self._class_name,
                                                        self._object_id))
        else:
            options = dict(self._options)  # make a local copy
            if self._where:
                # JSON encode WHERE values
                where = json.dumps(self._where)
                options.update({'where': where})

            response = self.__class__.GET('/%s' % self._class_name, **options)

        if single_result:
            return Object(self._class_name, response)
        else:
            return [Object(self._class_name, result)
                        for result in response['results']]


class UserQuery(Query):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'users'])
    QUERY_CLASS = User


class InstallationQuery(Query):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'installations'])
    QUERY_CLASS = Installation

    def _fetch(self):
        options = dict(self._options)  # make a local copy
        if self._where:
            # JSON encode WHERE values
            where = json.dumps(self._where)
            options.update({'where': where})

        extra_headers = {'X-Parse-Master-Key': MASTER_KEY}
        response = self.__class__.GET('', extra_headers=extra_headers,
                                        **options)
        return [self.__class__.QUERY_CLASS(**result)
                    for result in response['results']]
