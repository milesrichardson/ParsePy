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

import json
import collections
import copy


class QueryResourceDoesNotExist(Exception):
    '''Query returned no results'''
    pass


class QueryResourceMultipleResultsReturned(Exception):
    '''Query was supposed to return unique result, returned more than one'''
    pass


class QueryManager(object):
    def __init__(self, model_class):
        self.model_class = model_class

    def _fetch(self, **kw):
        klass = self.model_class
        uri = self.model_class.ENDPOINT_ROOT
        return [klass(**it) for it in klass.GET(uri, **kw).get('results')]

    def all(self):
        return Queryset(self)

    def where(self, **kw):
        return self.all().where(**kw)

    def lt(self, name, value):
        return self.all().lt(name=value)

    def lte(self, name, value):
        return self.all().lte(name=value)

    def ne(self, name, value):
        return self.all().ne(name=value)

    def gt(self, name, value):
        return self.all().gt(name=value)

    def gte(self, name, value):
        return self.all().gte(name=value)

    def fetch(self):
        return self.all().fetch()

    def get(self, **kw):
        return self.where(**kw).get()


class QuerysetMetaclass(type):
    """metaclass to add the dynamically generated comparison functions"""
    def __new__(cls, name, bases, dct):
        cls = super(QuerysetMetaclass, cls).__new__(cls, name, bases, dct)

        # add comparison functions and option functions
        for fname in ['lt', 'lte', 'gt', 'gte', 'ne']:
            def func(self, fname=fname, **kwargs):
                s = copy.deepcopy(self)
                for name, value in kwargs.items():
                    s._where[name]['$' + fname] = value
                return s
            setattr(cls, fname, func)

        for fname in ['limit', 'skip']:
            def func(self, value, fname=fname):
                s = copy.deepcopy(self)
                s._options[fname] = value
                return s
            setattr(cls, fname, func)

        return cls


class Queryset(object):
    __metaclass__ = QuerysetMetaclass

    def __init__(self, manager):
        self._manager = manager
        self._where = collections.defaultdict(dict)
        self._options = {}

    def __iter__(self):
        return iter(self._fetch())

    def _fetch(self):
        options = dict(self._options)  # make a local copy
        if self._where:
            # JSON encode WHERE values
            where = json.dumps(self._where)
            options.update({'where': where})

        return self._manager._fetch(**options)

    def where(self, **kw):
        return self.eq(**kw)

    def eq(self, **kw):
        for name, value in kw.items():
            self._where[name] = value
        return self

    def order_by(self, order, descending=False):
        # add a minus sign before the order value if descending == True
        self._options['order'] = descending and ('-' + order) or order
        return self

    def count(self):
        results = self._fetch()
        return len(results)

    def exists(self):
        results = self._fetch()
        return len(results) > 0

    def get(self):
        results = self._fetch()
        if len(results) == 0:
            raise QueryResourceDoesNotExist
        if len(results) >= 2:
            raise QueryResourceMultipleResultsReturned
        return results[0]

    def __repr__(self):
        return unicode(self._fetch())
