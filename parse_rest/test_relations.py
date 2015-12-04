#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
Contains unit tests for the Python Parse REST API wrapper
"""
from __future__ import print_function

import os
import sys
import subprocess
import unittest
import datetime
import six
from itertools import chain

from parse_rest.core import ResourceRequestNotFound
from parse_rest.core import ResourceRequestBadRequest
from parse_rest.connection import register, ParseBatcher
from parse_rest.datatypes import GeoPoint, Object, Function, Pointer, Relation
from parse_rest.user import User
from parse_rest import query
from parse_rest.installation import Push

try:
    import settings_local
except ImportError:
    sys.exit('You must create a settings_local.py file with APPLICATION_ID, ' \
                 'REST_API_KEY, MASTER_KEY variables set')

register(
    getattr(settings_local, 'APPLICATION_ID'),
    getattr(settings_local, 'REST_API_KEY'),
    master_key=getattr(settings_local, 'MASTER_KEY')
)

GLOBAL_JSON_TEXT = """{
    "applications": {
        "_default": {
            "link": "parseapi"
        },
        "parseapi": {
            "applicationId": "%s",
            "masterKey": "%s"
        }
    },
    "global": {
        "parseVersion": "1.1.16"
    }
}
"""


class Game(Object):
    pass


class GameScore(Object):
    pass


class TestRelation(unittest.TestCase):
    def setUp(self):
        self.score1 = GameScore(score=1337, player_name='John Doe', cheat_mode=False)
        self.score2 = GameScore(score=1337, player_name='Jane Doe', cheat_mode=False)
        self.score3 = GameScore(score=1337, player_name='Joan Doe', cheat_mode=False)
        self.score4 = GameScore(score=1337, player_name='Jeff Doe', cheat_mode=False)
        self.game = Game(name="foobar")
        self.game.save()
        self.rel = self.game.relation('scores')

    def tearDown(self):
        game_score = getattr(self.score1, 'score', None)
        game_name = getattr(self.game, 'name', None)
        if game_score:
            ParseBatcher().batch_delete(GameScore.Query.filter(score=game_score))
        if game_name:
            ParseBatcher().batch_delete(Game.Query.filter(name=game_name))
        
    def testRelationsAdd(self):
        """Add multiple objects to a relation."""
        self.rel.add(self.score1)
        scores = self.rel.query()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].player_name, 'John Doe')

        self.rel.add(self.score2)
        scores = self.rel.query()
        self.assertEqual(len(scores), 2)

        self.rel.add([self.score3, self.score4])
        scores = self.rel.query()
        self.assertEqual(len(scores), 4)

    def testRelationQueryLimitsToRelation(self):
        """Relational query limits results to objects in the relation."""
        self.rel.add([self.score1, self.score2])
        gamescore3 = GameScore(score=1337)
        gamescore3.save()
        # score saved but not associated with the game
        q = self.rel.query()
        scores = q.filter(score__gte=1337)
        self.assertEqual(len(scores), 2)

    def testRemoval(self):
        """Test if a specific object can be removed from a relation."""
        self.rel.add([self.score1, self.score2, self.score3])
        self.rel.remove(self.score1)
        self.rel.remove(self.score2)
        scores = self.rel.query()
        self.assertEqual(scores[0].player_name, 'Joan Doe')

    def testSchema(self):
        """Retrieve a schema for the class."""
        schema = Game.schema()
        self.assertEqual(schema['className'], 'Game')
        fields = schema['fields']
        self.assertEqual(fields['scores']['type'], 'Relation')

    def testWrongType(self):
        """You can't add two different classes to a relation."""
        with self.assertRaises(ResourceRequestBadRequest):
            self.rel.add(self.score1)
            self.rel.add(self.game)

    def testNoTypeSet(self):
        """Query can run before anything is added to the relation,
        if the schema online has already defined the relation.
        """
        scores = self.rel.query()
        self.assertEqual(len(scores), 0)


def run_tests():
    """Run all tests in the parse_rest package"""
    tests = unittest.TestLoader().loadTestsFromNames(['parse_rest.tests'])
    t = unittest.TextTestRunner(verbosity=1)
    t.run(tests)

if __name__ == "__main__":
    # command line
    unittest.main()
