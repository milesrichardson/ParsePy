import urllib, urllib2
import base64
import json

API_ROOT = 'https://api.parse.com/1/classes'

APPLICATION_ID = ''
MASTER_KEY = ''


class ParseBase(object):
    def _executeCall(self, uri, http_verb, data=None):
        url = API_ROOT + uri

        request = urllib2.Request(url, data)

        request.add_header('Content-type', 'application/json')

        auth_header =  "Basic %s" % base64.b64encode('%s:%s' % (APPLICATION_ID, MASTER_KEY))
        request.add_header("Authorization", auth_header)

        request.get_method = lambda: http_verb

        # TODO: add error handling for server response
        response = urllib2.urlopen(request)
        response_body = response.read()
        response_dict = json.loads(response_body)

        return response_dict


class ParseObject(ParseBase):
    def __init__(self, class_name):
        self._class_name = class_name
        self._object_id = None
        self._updated_at = None
        self._created_at = None

    def objectId(self):
        return self._object_id

    def updatedAt(self):
        return self._updated_at

    def createdAt(self):
        return self._created_at

    def save(self):
        if self._object_id:
            self._update()
        else:
            self._create()

    def _getJSONProperties(self):
        # exclude properties that start with an underscore
        properties = dict([(key, value) for key, value in self.__dict__.items() if key[0] != '_'])

        json_properties = json.dumps(properties)

        return json_properties


    def _create(self):
        # URL: /1/classes/<className>
        # HTTP Verb: POST

        uri = '/%s' % self._class_name

        data = self._getJSONProperties()

        response_dict = self._executeCall(uri, 'POST', data)
        
        self._created_at = self._updated_at = response_dict['createdAt']
        self._object_id = response_dict['objectId']

    def _update(self):
        # URL: /1/classes/<className>/<objectId>
        # HTTP Verb: PUT

        uri = '/%s/%s' % (self._class_name, self._object_id)

        data = self._getJSONProperties()

        response_dict = self._executeCall(uri, 'PUT', data)

        self._updated_at = response_dict['updatedAt']


class ParseQuery(ParseBase):
    def __init__(self, class_name):
        self.class_name = class_name
    
    def get(self, object_id):
        # URL: /1/classes/<className>/<objectId>
        # HTTP Verb: GET

        uri = '/%s/%s' % (self.class_name, object_id)

        response_dict = self._executeCall(uri, 'GET')

        new_parse_obj = ParseObject(self.class_name)
        new_parse_obj._object_id = response_dict['objectId']
        new_parse_obj._created_at = response_dict['createdAt']
        new_parse_obj._updated_at = response_dict['updatedAt']

        del response_dict['objectId']
        del response_dict['createdAt']
        del response_dict['updatedAt']

        new_parse_obj.__dict__.update(response_dict)

        return new_parse_obj



