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
from user import User


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

    def testCanUpdateExistingObject(self):
        self.sao_paulo.save()
        self.sao_paulo.country = 'Brazil'
        self.sao_paulo.save()

        city = City.Query.where(name='São Paulo').get()
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
            user = User.signup(self.username, self.password)
        except:
            user = User.Query.get(username=self.username)
        return user

    def _destroy_user(self):
        user = self._get_logged_user()
        user and user.delete()

    def _get_logged_user(self):
        if User.Query.where(username=self.username).exists():
            return User.login(self.username, self.password)
        else:
            return self._get_user()

    def setUp(self):
        self.username = TestUser.USERNAME
        self.password = TestUser.PASSWORD

        try:
            u = User.login(self.USERNAME, self.PASSWORD)
        except parse_rest.ResourceRequestNotFound as e:
            # if the user doesn't exist, that's fine
            return
        u.delete()

    def tearDown(self):
        self._destroy_user()

    def testCanSignUp(self):
        self._destroy_user()
        user = User.signup(self.username, self.password)
        self.assert_(user is not None)

    def testCanLogin(self):
        self._get_user()  # User should be created here.
        user = User.login(self.username, self.password)
        self.assert_(user.is_authenticated(), 'Login failed')

    def testCanUpdate(self):
        user = self._get_logged_user()
        phone_number = '555-5555'

        # add phone number and save
        user.phone = phone_number
        user.save()

        self.assert_(User.Query.where(phone=phone_number).exists(),
                     'Failed to update user data. New info not on Parse')

    def testCanQueryBySession(self):
        User.signup(self.username, self.password)
        logged = User.login(self.username, self.password)
        queried = User.Query.where(sessionToken=logged.sessionToken).get()
        self.assert_(queried.objectId == logged.objectId,
                     'Could not find user %s by session' % logged.username)

if __name__ == "__main__":
    # command line
    unittest.main()
