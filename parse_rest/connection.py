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

from six.moves.urllib.request import Request, urlopen
from six.moves.urllib.error import HTTPError
from six.moves.urllib.parse import urlencode

import json

from parse_rest import core

API_ROOT = 'https://api.parse.com/1'
ACCESS_KEYS = {}


# Connection can sometimes hang forever on SSL handshake
CONNECTION_TIMEOUT = 60


def register(app_id, rest_key, **kw):
    global ACCESS_KEYS
    ACCESS_KEYS = {
        'app_id': app_id,
        'rest_key': rest_key
        }
    ACCESS_KEYS.update(**kw)


class SessionToken:
    def __init__(self, token):
        global ACCESS_KEYS
        self.token = token

    def __enter__(self):
        ACCESS_KEYS.update({'session_token': self.token})

    def __exit__(self, type, value, traceback):
        ACCESS_KEYS['session_token']


def master_key_required(func):
    '''decorator describing methods that require the master key'''
    def ret(obj, *args, **kw):
        conn = ACCESS_KEYS
        if not (conn and conn.get('master_key')):
            message = '%s requires the master key' % func.__name__
            raise core.ParseError(message)
        func(obj, *args, **kw)
    return ret

# Using this as "default=" argument solve the problem with Datetime object not being JSON serializable
def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


class ParseBase(object):
    ENDPOINT_ROOT = API_ROOT

    @classmethod
    def execute(cls, uri, http_verb, extra_headers=None, batch=False, body=None, **kw):
        """
        if batch == False, execute a command with the given parameters and
        return the response JSON.
        If batch == True, return the dictionary that would be used in a batch
        command.
        """
        if batch:
            ret = {"method": http_verb, "path": uri.split("parse.com", 1)[1]}
            if kw:
                ret["body"] = kw
            return ret

        if not ('app_id' in ACCESS_KEYS and 'rest_key' in ACCESS_KEYS):
            raise core.ParseError('Missing connection credentials')

        app_id = ACCESS_KEYS.get('app_id')
        rest_key = ACCESS_KEYS.get('rest_key')
        master_key = ACCESS_KEYS.get('master_key')

        url = uri if uri.startswith(API_ROOT) else cls.ENDPOINT_ROOT + uri
        if body is None:
            data = kw and json.dumps(kw, default=date_handler) or "{}"
        else:
            data = body
        if http_verb == 'GET' and data:
            url += '?%s' % urlencode(kw)
            data = None
        else:
            data = data.encode('utf-8')

        headers = {
            'Content-type': 'application/json',
            'X-Parse-Application-Id': app_id,
            'X-Parse-REST-API-Key': rest_key
        }
        headers.update(extra_headers or {})

        request = Request(url, data, headers)
        
        if ACCESS_KEYS.get('session_token'):
            request.add_header('X-Parse-Session-Token', ACCESS_KEYS.get('session_token'))

        if master_key and 'X-Parse-Session-Token' not in headers.keys():
            request.add_header('X-Parse-Master-Key', master_key)

        request.get_method = lambda: http_verb

        try:
            response = urlopen(request, timeout=CONNECTION_TIMEOUT)
        except HTTPError as e:
            exc = {
                400: core.ResourceRequestBadRequest,
                401: core.ResourceRequestLoginRequired,
                403: core.ResourceRequestForbidden,
                404: core.ResourceRequestNotFound
                }.get(e.code, core.ParseError)
            raise exc(e.read())

        return json.loads(response.read().decode('utf-8'))

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

    @classmethod
    def drop(cls):
        return cls.POST("%s/schemas/%s" % (API_ROOT, cls.__name__),
                        _method="DELETE", _ClientVersion="browser")


class ParseBatcher(ParseBase):
    """Batch together create, update or delete operations"""
    ENDPOINT_ROOT = '/'.join((API_ROOT, 'batch'))

    def batch(self, methods):
        """
        Given a list of create, update or delete methods to call, call all
        of them in a single batch operation.
        """
        methods = list(methods) # methods can be iterator
        if not methods:
            #accepts also empty list (or generator) - it allows call batch directly with query result (eventually empty)
            return
        queries, callbacks = list(zip(*[m(batch=True) for m in methods]))
        # perform all the operations in one batch
        responses = self.execute("", "POST", requests=queries)
        # perform the callbacks with the response data (updating the existing
        # objets, etc)
        for callback, response in zip(callbacks, responses):
            if "success" in response:
                callback(response["success"])
            else:
                raise core.ParseError(response["error"])

    def batch_save(self, objects):
        """save a list of objects in one operation"""
        self.batch(o.save for o in objects)

    def batch_delete(self, objects):
        """delete a list of objects in one operation"""
        self.batch(o.delete for o in objects)
