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

    def all(self):
        return Queryset(self)

    def where(self, **kw):
        return Queryset(self).where(**kw)

    def get(self, **kw):
        return Queryset(self).where(**kw).get()


class QuerysetMetaclass(type):
    """metaclass to add the dynamically generated comparison functions"""
    def __new__(cls, name, bases, dct):
        cls = super(QuerysetMetaclass, cls).__new__(cls, name, bases, dct)

        # add comparison functions and option functions
        for fname in ["lt", "lte", "gt", "gte", "ne"]:
            def func(self, name, value, fname=fname):
                s = copy.deepcopy(self)
                s._where[name]["$" + fname] = value
                return s
            setattr(cls, fname, func)

        for fname in ["limit", "skip"]:
            def func(self, value, fname=fname):
                s = copy.deepcopy(self)
                s._options[fname] = value
                return s
            setattr(cls, fname, func)

        return cls


class Queryset(object):
    __metaclass__ = QuerysetMetaclass

    def __init__(self, model_class):
        self.model_class = model_class
        self._where = collections.defaultdict(dict)
        self._options = {}

    def __iter__(self):
        return iter(self._fetch())

    def copy_method(f):
        """Represents functions that have to make a copy before running"""
        def newf(self, *a, **kw):
            s = copy.deepcopy(self)
            return f(s, *a, **kw)
        return newf

    def all(self):
        """return as a list"""
        return list(self)

    @copy_method
    def where(self, **kw):
        for key, value in kw.items():
            self = self.eq(key, value)
        return self

    @copy_method
    def eq(self, name, value):
        self._where[name] = value
        return self

    @copy_method
    def order(self, order, descending=False):
        # add a minus sign before the order value if descending == True
        self._options['order'] = descending and ('-' + order) or order
        return self

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

    def _fetch(self):
        options = dict(self._options)  # make a local copy
        if self._where:
            # JSON encode WHERE values
            where = json.dumps(self._where)
            options.update({'where': where})

        klass = self.model_class
        uri = self.model_class.ENDPOINT_ROOT
        return [klass(**it) for it in klass.GET(uri, **options).get('results')]
