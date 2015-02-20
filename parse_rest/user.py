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


from parse_rest.core import ResourceRequestLoginRequired, ParseError
from parse_rest.connection import API_ROOT
from parse_rest.datatypes import ParseResource, ParseType
from parse_rest.query import QueryManager


def login_required(func):
    '''decorator describing User methods that need to be logged in'''
    def ret(obj, *args, **kw):
        if not hasattr(obj, 'sessionToken'):
            message = '%s requires a logged-in session' % func.__name__
            raise ResourceRequestLoginRequired(message)
        return func(obj, *args, **kw)
    return ret


class User(ParseResource):
    '''
    A User is like a regular Parse object (can be modified and saved) but
    it requires additional methods and functionality
    '''
    ENDPOINT_ROOT = '/'.join([API_ROOT, 'users'])
    PROTECTED_ATTRIBUTES = ParseResource.PROTECTED_ATTRIBUTES + [
        'username', 'sessionToken', 'emailVerified']

    def is_authenticated(self):
        return self.sessionToken is not None

    def authenticate(self, password=None, session_token=None):
        if self.is_authenticated(): return

        if password is not None:
            self = User.login(self.username, password)

        user = User.Query.get(objectId=self.objectId)
        if user.objectId == self.objectId and user.sessionToken == session_token:
            self.sessionToken = session_token

    @login_required
    def session_header(self):
        return {'X-Parse-Session-Token': self.sessionToken}

    @login_required
    def save(self, batch=False):
        session_header = {'X-Parse-Session-Token': self.sessionToken}
        url = self._absolute_url
        data = self._to_native()

        response = User.PUT(url, extra_headers=session_header, batch=batch, **data)

        def call_back(response_dict):
            self.updatedAt = response_dict['updatedAt']

        if batch:
            return response, call_back
        else:
            call_back(response)

    @login_required
    def delete(self):
        session_header = {'X-Parse-Session-Token': self.sessionToken}
        return User.DELETE(self._absolute_url, extra_headers=session_header)

    @classmethod
    def signup(cls, username, password, **kw):
        response_data = User.POST('', username=username, password=password, **kw)
        response_data.update({'username': username})
        return cls(**response_data)

    @classmethod
    def login(cls, username, passwd):
        login_url = '/'.join([API_ROOT, 'login'])
        return cls(**User.GET(login_url, username=username, password=passwd))

    @classmethod
    def login_auth(cls, auth):
        login_url = User.ENDPOINT_ROOT
        return cls(**User.POST(login_url, authData=auth))

    @classmethod
    def current_user(cls):
        user_url = '/'.join([API_ROOT, 'users/me'])
        return cls(**User.GET(user_url))

    @staticmethod
    def request_password_reset(email):
        '''Trigger Parse\'s Password Process. Return True/False
        indicate success/failure on the request'''

        url = '/'.join([API_ROOT, 'requestPasswordReset'])
        try:
            User.POST(url, email=email)
            return True
        except ParseError:
            return False

    def _to_native(self):
        return dict([(k, ParseType.convert_to_parse(v, as_pointer=True))
                     for k, v in self._editable_attrs.items()])

    @property
    def className(self):
        return '_User'

    def __repr__(self):
        return '<User:%s (Id %s)>' % (getattr(self, 'username', None), self.objectId)
    
    def removeRelation(self, key, className, objectsId):
        self.manageRelation('RemoveRelation', key, className, objectsId)

    def addRelation(self, key, className, objectsId):
        self.manageRelation('AddRelation', key, className, objectsId)

    def manageRelation(self, action, key, className, objectsId):
        objects = [{
                    "__type": "Pointer",
                    "className": className,
                    "objectId": objectId
                    } for objectId in objectsId]

        payload = {
            key: {
                 "__op": action,
                 "objects": objects
                }
            }
        self.__class__.PUT(self._absolute_url, **payload)
        self.__dict__[key] = ''


User.Query = QueryManager(User)
