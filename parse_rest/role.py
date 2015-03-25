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
from parse_rest.datatypes import Object
from parse_rest.query import QueryManager


class Role(Object):
    '''
    A Role is like a regular Parse object (can be modified and saved) but
    it requires additional methods and functionality
    '''
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'roles'])

    @property
    def className(self):
        return '_Role'

    def __repr__(self):
        return '<Role:%s (Id %s)>' % (getattr(self, 'name', None), self.objectId)

    @classmethod
    def set_endpoint_root(cls):
        return cls.ENDPOINT_ROOT


Role.Query = QueryManager(Role)
