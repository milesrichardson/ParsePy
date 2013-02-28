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

API_ROOT = 'https://api.parse.com/1'


class ParseError(Exception):
    '''Base exceptions from requests made to Parse'''
    pass


class ResourceRequestBadRequest(ParseError):
    '''Request returns a 400'''
    pass


class ResourceRequestLoginRequired(ParseError):
    '''Request returns a 401'''
    pass


class ResourceRequestForbidden(ParseError):
    '''Request returns a 403'''
    pass


class ResourceRequestNotFound(ParseError):
    '''Request returns a 404'''
    pass

def master_key_required(func):
    '''decorator describing methods that require the master key'''
    def ret(obj, *args, **kw):
        conn = ParseBase.CONNECTION
        if not (conn and conn.get('master_key')):
            message = '%s requires the master key' % func.__name__
            raise ParseError(message)
        func(obj, *args, **kw)
    return ret

class ParseBase(object):
    ENDPOINT_ROOT = API_ROOT

    @classmethod
    def register(cls, app_id, rest_key, **kw):
        ParseBase.CONNECTION = {
            'app_id': app_id,
            'rest_key': rest_key
            }
        ParseBase.CONNECTION.update(**kw)


    @classmethod
    def execute(cls, uri, http_verb, extra_headers=None, **kw):
        if not ParseBase.CONNECTION:
            raise ParseError('Missing connection credentials')


        app_id = ParseBase.CONNECTION.get('app_id')
        rest_key = ParseBase.CONNECTION.get('rest_key')
        master_key = ParseBase.CONNECTION.get('master_key')

        headers = extra_headers or {}
        url = uri if uri.startswith(API_ROOT) else cls.ENDPOINT_ROOT + uri
        data = kw and json.dumps(kw) or "{}"
        if http_verb == 'GET' and data:
            url += '?%s' % urllib.urlencode(kw)
            data = None

        request = urllib2.Request(url, data, headers)
        request.add_header('Content-type', 'application/json')
        request.add_header('X-Parse-Application-Id', app_id)
        request.add_header('X-Parse-REST-API-Key', rest_key)

        if master_key: request.add_header('X-Parse-Master-Key', master_key)

        request.get_method = lambda: http_verb

        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            exc = {
                400: ResourceRequestBadRequest,
                401: ResourceRequestLoginRequired,
                403: ResourceRequestForbidden,
                404: ResourceRequestNotFound
                }.get(e.code, ParseError)
            raise exc(e.read())

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


__all__ = [
    'ParseBase', 'ResourceRequestBadRequest', 'ResourceLoginRequired',
    'ResourceRequestForbidden', 'ResourceRequestNotFound'
    ]
