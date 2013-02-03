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


class Queryset(object):

    def __init__(self, manager):
        self._manager = manager
        self._where = collections.defaultdict(dict)
        self._options = {}

    def __iter__(self):
        results = getattr(self, '_results', self._fetch())
        self._results = results
        if len(self._results) == 0:
            raise StopIteration
        yield self._results.pop(0)

    def where(self, **kw):
        for key, value in kw.items():
            self.eq(key, value)
        return self

    def eq(self, name, value):
        self._where[name] = value
        return self

    # It's tempting to generate the comparison functions programatically,
    # but probably not worth the decrease in readability of the code.
    def lt(self, name, value):
        self._where[name]['$lt'] = value
        return self

    def lte(self, name, value):
        self._where[name]['$lte'] = value
        return self

    def gt(self, name, value):
        self._where[name]['$gt'] = value
        return self

    def gte(self, name, value):
        self._where[name]['$gte'] = value
        return self

    def ne(self, name, value):
        self._where[name]['$ne'] = value
        return self

    def order(self, order, decending=False):
        # add a minus sign before the order value if decending == True
        self._options['order'] = decending and ('-' + order) or order
        return self

    def limit(self, limit):
        self._options['limit'] = limit
        return self

    def skip(self, skip):
        self._options['skip'] = skip
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

        klass = self._manager.model_class
        uri = self._manager.model_class.ENDPOINT_ROOT
        return [klass(**it) for it in klass.GET(uri, **options).get('results')]
