#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
Contains unit tests for the Python Parse REST API wrapper
"""

import os
import subprocess
import unittest
import urllib2
import datetime

import __init__ as parse_rest
from __init__ import GeoPoint, Object
import query


try:
    import settings_local
except ImportError:
    raise ImportError('You must create a settings_local.py file with an ' +
                      'APPLICATION_ID, REST_API_KEY, and a MASTER_KEY ' +
                      'to run tests.')

parse_rest.APPLICATION_ID = getattr(settings_local, 'APPLICATION_ID', '')
parse_rest.REST_API_KEY = getattr(settings_local, 'REST_API_KEY', '')
parse_rest.MASTER_KEY = getattr(settings_local, 'MASTER_KEY', '')

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


class GameScore(Object):
    pass


class City(Object):
    pass


class Review(Object):
    pass


class CollectedItem(Object):
    pass


class TestObject(unittest.TestCase):
    def setUp(self):
        self.score = GameScore(
            score=1337, player_name='John Doe', cheat_mode=False
            )
        self.sao_paulo = City(
            name='São Paulo', location=GeoPoint(-23.5, -46.6167)
            )

    def tearDown(self):
        city_name = getattr(self.sao_paulo, 'name', None)
        game_score = getattr(self.score, 'score', None)
        if city_name:
            for city in City.Query.where(name=city_name):
                city.delete()

        if game_score:
            for score in GameScore.Query.where(score=game_score):
                score.delete()

    def testCanInitialize(self):
        self.assert_(self.score.score == 1337, 'Could not set score')

    def testCanInstantiateParseType(self):
        self.assert_(self.sao_paulo.location.latitude == -23.5)

    def testCanCreateNewObject(self):
        self.score.save()
        self.assert_(self.score.objectId is not None, 'Can not create object')

        self.assert_(type(self.score.objectId) == unicode)
        self.assert_(type(self.score.createdAt) == datetime.datetime)
        self.assert_(GameScore.Query.where(
                        objectId=self.score.objectId).exists(),
                        'Can not create object')

    def testCanUpdateExistingObject(self):
        self.sao_paulo.save()
        self.sao_paulo.country = 'Brazil'
        self.sao_paulo.save()
        self.assert_(type(self.sao_paulo.updatedAt) == datetime.datetime)

        city = City.Query.get(name='São Paulo')
        self.assert_(city.country == 'Brazil', 'Could not update object')

    def testCanDeleteExistingObject(self):
        self.score.save()
        object_id = self.score.objectId
        self.score.delete()
        self.assert_(not GameScore.Query.where(objectId=object_id).exists(),
                     'Failed to delete object %s on Parse ' % self.score)

    def testCanIncrementField(self):
        previous_score = self.score.score
        self.score.save()
        self.score.increment('score')
        self.assert_(GameScore.Query.where(score=previous_score + 1).exists(),
                     'Failed to increment score on backend')

    def testAssociatedObject(self):
        """test saving and associating a different object"""
        collectedItem = CollectedItem(type="Sword", isAwesome=True)
        collectedItem.save()
        self.score.item = collectedItem
        self.score.save()

        # get the object, see if it has saved
        qs = GameScore.Query.get(objectId=self.score.objectId)
        self.assert_(isinstance(qs.item, Object),
                     "Associated CollectedItem is not of correct class")
        self.assert_(qs.item.type == "Sword",
                   "Associated CollectedItem does not have correct attributes")


class TestQuery(unittest.TestCase):
    """Tests of an object's Queryset"""
    def setUp(self):
        """save a bunch of GameScore objects with varying scores"""
        # first delete any that exist
        for s in GameScore.Query.all():
            s.delete()

        self.scores = [GameScore(score=s, player_name='John Doe')
                            for s in range(1, 6)]
        for s in self.scores:
            s.save()

    def testExists(self):
        """test the Queryset.exists() method"""
        for s in range(1, 6):
            self.assert_(GameScore.Query.where(score=s).exists(),
                         "exists giving false negative")
        self.assert_(not GameScore.Query.where(score=10).exists(),
                     "exists giving false positive")

    def testWhereGet(self):
        """test the Queryset.where() and Queryset.get() methods"""
        for s in self.scores:
            qobj = GameScore.Query.where(objectId=s.objectId).get()
            self.assert_(qobj.objectId == s.objectId,
                         "Getting object with .where() failed")
            self.assert_(qobj.score == s.score,
                         "Getting object with .where() failed")

        # test the two exceptions get can raise
        self.assertRaises(query.QueryResourceDoesNotExist,
                          GameScore.Query.all().gt(score=20).get)
        self.assertRaises(query.QueryResourceMultipleResultsReturned,
                          GameScore.Query.all().gt(score=3).get)

    def testComparisons(self):
        """test comparison operators- gt, gte, lt, lte, ne"""
        scores_gt_3 = list(GameScore.Query.all().gt(score=3))
        self.assertEqual(len(scores_gt_3), 2)
        self.assert_(all([s.score > 3 for s in scores_gt_3]))

        scores_gte_3 = list(GameScore.Query.all().gte(score=3))
        self.assertEqual(len(scores_gte_3), 3)
        self.assert_(all([s.score >= 3 for s in scores_gt_3]))

        scores_lt_4 = list(GameScore.Query.all().lt(score=4))
        self.assertEqual(len(scores_lt_4), 3)
        self.assert_(all([s.score < 4 for s in scores_lt_4]))

        scores_lte_4 = list(GameScore.Query.all().lte(score=4))
        self.assertEqual(len(scores_lte_4), 4)
        self.assert_(all([s.score <= 4 for s in scores_lte_4]))

        scores_ne_2 = list(GameScore.Query.all().ne(score=2))
        self.assertEqual(len(scores_ne_2), 4)
        self.assert_(all([s.score != 2 for s in scores_ne_2]))

        # test chaining
        lt_4_gt_2 = list(GameScore.Query.all().lt(score=4).gt(score=2))
        self.assert_(len(lt_4_gt_2) == 1, "chained lt+gt not working")
        self.assert_(lt_4_gt_2[0].score == 3, "chained lt+gt not working")
        q = GameScore.Query.all().gt(score=3).lt(score=3)
        self.assert_(not q.exists(), "chained lt+gt not working")

    def testOptions(self):
        """test three options- order, limit, and skip"""
        scores_ordered = list(GameScore.Query.all().order_by("score"))
        self.assertEqual([s.score for s in scores_ordered],
                         [1, 2, 3, 4, 5])

        scores_ordered_desc = list(GameScore.Query.all().order_by("score", descending=True))
        self.assertEqual([s.score for s in scores_ordered_desc],
                         [5, 4, 3, 2, 1])

        scores_limit_3 = list(GameScore.Query.all().limit(3))
        self.assert_(len(scores_limit_3) == 3, "Limit did not return 3 items")

        scores_skip_3 = list(GameScore.Query.all().skip(3))
        self.assert_(len(scores_skip_3) == 2, "Skip did not return 2 items")

    def tearDown(self):
        """delete all GameScore objects"""
        for s in GameScore.Query.all():
            s.delete()


class TestFunction(unittest.TestCase):
    def setUp(self):
        """create and deploy cloud functions"""
        original_dir = os.getcwd()
        cloud_function_dir = os.path.join(os.path.split(__file__)[0],
                                          "cloudcode")
        os.chdir(cloud_function_dir)
        # write the config file
        with open("config/global.json", "w") as outf:
            outf.write(GLOBAL_JSON_TEXT % (settings_local.APPLICATION_ID,
                                           settings_local.MASTER_KEY))
        try:
            subprocess.call(["parse", "deploy"])
        except OSError:
            raise OSError("parse command line tool must be installed " +
                          "(see https://www.parse.com/docs/cloud_code_guide)")
        os.chdir(original_dir)

    def tearDown(self):
        for review in Review.Query.all():
            review.delete()

    def test_simple_functions(self):
        """test hello world and averageStars functions"""
        # test the hello function- takes no arguments
        hello_world_func = parse_rest.Function("hello")
        ret = hello_world_func()
        self.assertEqual(ret["result"], u"Hello world!")

        # Test the averageStars function- takes simple argument
        r1 = Review(movie="The Matrix", stars=5,
                    comment="Too bad they never made any sequels.")
        r1.save()
        r2 = Review(movie="The Matrix", stars=4, comment="It's OK.")
        r2.save()

        star_func = parse_rest.Function("averageStars")
        ret = star_func(movie="The Matrix")
        self.assertAlmostEqual(ret["result"], 4.5)


class TestUser(unittest.TestCase):
    USERNAME = "dhelmet@spaceballs.com"
    PASSWORD = "12345"

    def _get_user(self):
        try:
            user = parse_rest.User.signup(self.username, self.password)
        except:
            user = parse_rest.User.Query.get(username=self.username)
        return user

    def _destroy_user(self):
        user = self._get_logged_user()
        user and user.delete()

    def _get_logged_user(self):
        if parse_rest.User.Query.where(username=self.username).exists():
            return parse_rest.User.login(self.username, self.password)
        else:
            return self._get_user()

    def setUp(self):
        self.username = TestUser.USERNAME
        self.password = TestUser.PASSWORD

        try:
            u = parse_rest.User.login(self.USERNAME, self.PASSWORD)
        except parse_rest.ResourceRequestNotFound as e:
            # if the user doesn't exist, that's fine
            return
        u.delete()

    def tearDown(self):
        self._destroy_user()

    def testCanSignUp(self):
        self._destroy_user()
        user = parse_rest.User.signup(self.username, self.password)
        self.assert_(user is not None)

    def testCanLogin(self):
        self._get_user()  # User should be created here.
        user = parse_rest.User.login(self.username, self.password)
        self.assert_(user.is_authenticated(), 'Login failed')

    def testCanUpdate(self):
        user = self._get_logged_user()
        phone_number = '555-5555'

        # add phone number and save
        user.phone = phone_number
        user.save()

        self.assert_(parse_rest.User.Query.where(phone=phone_number).exists(),
                     'Failed to update user data. New info not on Parse')

if __name__ == "__main__":
    # command line
    unittest.main()
