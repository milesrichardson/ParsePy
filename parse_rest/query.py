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
import copy
import collections


class QueryError(Exception):
    '''Query error base class'''

    def __init__(self, message, status_code=None):
        super(QueryError, self).__init__(message)
        if status_code:
            self.status_code = status_code


class QueryResourceDoesNotExist(QueryError):
    '''Query returned no results'''
    pass


class QueryResourceMultipleResultsReturned(QueryError):
    '''Query was supposed to return unique result, returned more than one'''
    pass


class QueryManager(object):

    def __init__(self, model_class):
        self.model_class = model_class

    def _fetch(self, **kw):
        klass = self.model_class
        uri = self.model_class.ENDPOINT_ROOT
        return [klass(**it) for it in klass.GET(uri, **kw).get('results')]

    def _count(self, **kw):
        kw.update({"count": 1})
        return self.model_class.GET(self.model_class.ENDPOINT_ROOT, **kw).get('count')

    def all(self):
        return Queryset(self)

    def filter(self, **kw):
        return self.all().filter(**kw)

    def fetch(self):
        return self.all().fetch()

    def get(self, **kw):
        return self.filter(**kw).get()


class Queryset(object):

    OPERATORS = [
        'lt', 'lte', 'gt', 'gte', 'ne', 'in', 'nin', 'exists', 'select', 'dontSelect', 'all', 'relatedTo', 'nearSphere'
    ]

    @staticmethod
    def convert_to_parse(value):
        from parse_rest.datatypes import ParseType
        return ParseType.convert_to_parse(value, as_pointer=True)

    @classmethod
    def extract_filter_operator(cls, parameter):
        for op in cls.OPERATORS:
            underscored = '__%s' % op
            if parameter.endswith(underscored):
                return parameter[:-len(underscored)], op
        return parameter, None

    def __init__(self, manager):
        self._manager = manager
        self._where = collections.defaultdict(dict)
        self._select_related = []
        self._options = {}
        self._result_cache = None

    def __deepcopy__(self, memo):
        q = self.__class__(self._manager)
        q._where = copy.deepcopy(self._where, memo)
        q._options = copy.deepcopy(self._options, memo)
        q._select_related.extend(self._select_related)
        return q

    def __iter__(self):
        return iter(self._fetch())

    def __len__(self):
        #don't use count query for len operator
        #count doesn't return real size of result in all cases (eg if query contains skip option)
        return len(self._fetch())

    def __getitem__(self, key):
        if isinstance(key, slice):
            raise AttributeError("Slice is not supported for now.")
        return self._fetch()[key]

    def _fetch(self, count=False):
        if self._result_cache is not None:
            return len(self._result_cache) if count else self._result_cache
        """
        Return a list of objects matching query, or if count == True return
        only the number of objects matching.
        """
        options = dict(self._options)  # make a local copy
        if self._where:
            # JSON encode WHERE values
            options['where'] = json.dumps(self._where)
        if self._select_related:
            options['include'] = ','.join(self._select_related)
        if count:
            return self._manager._count(**options)

        self._result_cache = self._manager._fetch(**options)
        return self._result_cache

    def filter(self, **kw):
        q = copy.deepcopy(self)
        for name, value in kw.items():
            parse_value = Queryset.convert_to_parse(value)
            attr, operator = Queryset.extract_filter_operator(name)
            if operator is None:
                q._where[attr] = parse_value
            elif operator == 'relatedTo':
                q._where['$' + operator] = {'object': parse_value, 'key': attr}
            else:
                if not isinstance(q._where[attr], dict):
                    q._where[attr] = {}
                q._where[attr]['$' + operator] = parse_value
        return q

    def limit(self, value):
        q = copy.deepcopy(self)
        q._options['limit'] = int(value)
        return q

    def skip(self, value):
        q = copy.deepcopy(self)
        q._options['skip'] = int(value)
        return q

    def order_by(self, order, descending=False):
        q = copy.deepcopy(self)
        # add a minus sign before the order value if descending == True
        q._options['order'] = descending and ('-' + order) or order
        return q

    def select_related(self, *fields):
        q = copy.deepcopy(self)
        q._select_related.extend(fields)
        return q

    def count(self):
        return self._fetch(count=True)

    def exists(self):
        return bool(self)

    def get(self):
        results = self._fetch()
        if len(results) == 0:
            error_message = 'Query against %s returned no results' % (
                    self._manager.model_class.ENDPOINT_ROOT)
            raise QueryResourceDoesNotExist(error_message,
                                            status_code=404)
        if len(results) >= 2:
            error_message = 'Query against %s returned multiple results' % (
                    self._manager.model_class.ENDPOINT_ROOT)
            raise QueryResourceMultipleResultsReturned(error_message,
                                                       status_code=404)
        return results[0]

    def __repr__(self):
        return repr(self._fetch())
