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

from parse_rest.connection import API_ROOT
from parse_rest.datatypes import ParseResource
from parse_rest.query import QueryManager


class Installation(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'installations'])

    @classmethod
    def _get_installation_url(cls, installation_id):
        """
        Get the URL for RESTful operations on this particular installation
        """
        return '/'.join([cls.ENDPOINT_ROOT, installation_id])

    @classmethod
    def update_channels(cls, installation_id, channels_to_add=set(),
                        channels_to_remove=set(), **kw):
        """
        Allow an application to manually subscribe or unsubscribe an
        installation to a certain push channel in a unified operation.

        this is based on:
        https://www.parse.com/docs/rest#installations-updating

        installation_id: the installation id you'd like to add a channel to
        channels_to_add: the name of the channel you'd like to subscribe the user to
        channels_to_remove: the name of the channel you'd like to unsubscribe the user from

        """
        installation_url = cls._get_installation_url(installation_id)
        current_config = cls.GET(installation_url)

        new_channels = list(set(current_config['channels']).union(channels_to_add).difference(channels_to_remove))

        cls.PUT(installation_url, channels=new_channels)


class Push(ParseResource):
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'push'])

    @classmethod
    def _send(cls, data, where=None, **kw):
        if where:
            kw['where'] = where

            # allow channels to be specified even if "where" is as well
            if "channels" in kw:
                kw['where']["channels"] = kw.pop("channels")

        return cls.POST('', data=data, **kw)

    @classmethod
    def alert(cls, data, where=None, **kw):
        cls._send(data, where=where, **kw)

    @classmethod
    def message(cls, message, where=None, **kw):
        cls._send({'alert': message}, where=where, **kw)

Installation.Query = QueryManager(Installation)
