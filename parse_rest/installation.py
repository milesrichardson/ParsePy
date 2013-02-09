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

import __init__ as parse_rest
from __init__ import API_ROOT, ParseResource
from query import QueryManager


class InstallationManager(QueryManager):
    def __init__(self):
        self._model_class = Installation

    def _fetch(self, **kw):
        kw['extra_headers'] = {'X-Parse-Master-Key': parse_rest.MASTER_KEY}
        response = Installation.GET(Installation.ENDPOINT_ROOT, **kw)
        return [Installation(**it) for it in response.get('results')]

class Installation(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'installations'])


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

Installation.Query = InstallationManager()
