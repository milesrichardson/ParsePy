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
from parse_rest.core import ParseError
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


class TestNoRelation(unittest.TestCase):
    def setUp(self):
        try:
            Game.schema_delete_field('scores')
        except ResourceRequestBadRequest:
            # fails if the field doesn't exist
            pass
        self.game = Game(name="foobar")
    
    def testQueryWithNoRelationOnline(self):
        """If the online schema lacks the relation, we cannot query."""
        with self.assertRaises(KeyError):
            rel = self.game.relation('scores')
            rel.query()


class TestRelation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # prime the schema with a relation field for GameScore
        score1 = GameScore(score=1337, player_name='John Doe', cheat_mode=False)
        game = Game(name="foobar")
        game.save()
        rel = game.relation('scores')
        rel.add(score1)

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

    @classmethod
    def tearDownClass(cls):
        Game.schema_delete_field('scores')

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
        """Adding wrong type fails silently."""
        self.rel.add(self.score1)
        self.rel.add(self.score2)
        self.rel.add(self.game)  # should fail to add this
        scores = self.rel.query()
        self.assertEqual(len(scores), 2)

    def testNoTypeSetParseHasColumn(self):
        """Query can run before anything is added to the relation,
        if the schema online has already defined the relation.
        """
        scores = self.rel.query()
        self.assertEqual(len(scores), 0)

    def testWrongColumnForRelation(self):
        """Should get a ParseError if we specify a relation on
        a column that is not a relation.
        """
        with self.assertRaises(ParseError):
            rel = self.game.relation("name")
            rel.query()

    def testNonexistentColumnForRelation(self):
        """Should get a ParseError if we specify a relation on
        a column that is not a relation.
        """
        with self.assertRaises(KeyError):
            rel = self.game.relation("nonexistent")
            rel.query()

    def testRepr(self):
        s = "*** %s ***" % (self.rel)
        self.assertRegex(s, '<Relation where .+ for .+>')

    def testWithParent(self):
        """Rehydrating a relation from an instance on the server.
        With_parent is called by relation() when the object was
        retrieved from the server. This test is for code coverage.
        """
        game2 = Game.Query.get(objectId=self.game.objectId)
        self.assertTrue(hasattr(game2, 'scores'))
        rel2 = game2.relation('scores')
        self.assertIsInstance(rel2, Relation)


def run_tests():
    """Run all tests in the parse_rest package"""
    tests = unittest.TestLoader().loadTestsFromNames(['parse_rest.tests'])
    t = unittest.TextTestRunner(verbosity=1)
    t.run(tests)

if __name__ == "__main__":
    # command line
    unittest.main()
