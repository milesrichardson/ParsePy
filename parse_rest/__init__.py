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

APPLICATION_ID = ''
REST_API_KEY = ''
MASTER_KEY = ''


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

        if APPLICATION_ID == "" or REST_API_KEY == "":
            raise ParseError("Must set parse_rest.APPLICATION_ID and " +
                             "parse_rest.REST_API_KEY")

        request = urllib2.Request(url, data, headers)
        request.add_header('Content-type', 'application/json')
        request.add_header("X-Parse-Application-Id", APPLICATION_ID)
        request.add_header("X-Parse-REST-API-Key", REST_API_KEY)

        request.get_method = lambda: http_verb

        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            raise {
                400: ResourceRequestBadRequest,
                401: ResourceRequestLoginRequired,
                403: ResourceRequestForbidden,
                404: ResourceRequestNotFound
                }.get(e.code, ParseError)

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
