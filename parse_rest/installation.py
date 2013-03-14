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

from connection import API_ROOT
from datatypes import ParseResource
from query import QueryManager


class Installation(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'installations'])


class Push(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'push'])

    @classmethod
    def send(cls, message, channels=None, type=None, push_time=None, expiration_interval=None, **kw):
        if type(message) == dict:
            data = message
        else:
            data = {'alert': message}
        targets = {}
        if push_time:
            targets["push_time"] = push_time
        if expiration_interval:
            targets["expiration_interval"] = expiration_interval
        if type:
            targets["type"] = type
        if channels:
            targets['channels'] = channels
        if kw:
            targets['where'] = kw
        return cls.POST('', data=data, **targets)


Installation.Query = QueryManager(Installation)
