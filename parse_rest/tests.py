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
from parse_rest.connection import register, ParseBatcher
from parse_rest.datatypes import GeoPoint, Object, Function, Pointer
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


class GameMap(Object):
    pass


class GameMode(Object):
    pass


class City(Object):
    pass


class Review(Object):
    pass


class CollectedItem(Object):
    pass


class TestObject(unittest.TestCase):
    def setUp(self):
        self.score = GameScore(score=1337, player_name='John Doe', cheat_mode=False)
        self.sao_paulo = City(name='São Paulo', location=GeoPoint(-23.5, -46.6167))
        self.collected_item = CollectedItem(type="Sword", isAwesome=True)

    def tearDown(self):
        city_name = getattr(self.sao_paulo, 'name', None)
        game_score = getattr(self.score, 'score', None)
        collected_item_type = getattr(self.collected_item, 'type', None)
        if city_name:
            ParseBatcher().batch_delete(City.Query.filter(name=city_name))
        if game_score:
            ParseBatcher().batch_delete(GameScore.Query.filter(score=game_score))
        if collected_item_type:
            ParseBatcher().batch_delete(CollectedItem.Query.filter(type=collected_item_type))
        
    def testCanInitialize(self):
        self.assertEqual(self.score.score, 1337, 'Could not set score')

    def testCanInstantiateParseType(self):
        self.assertEqual(self.sao_paulo.location.latitude, -23.5)

    def testFactory(self):
        self.assertEqual(Object.factory('_User'), User)
        self.assertEqual(Object.factory('GameScore'), GameScore)

    def testCanSaveDates(self):
        now = datetime.datetime.now()
        self.score.last_played = now
        self.score.save()
        self.assertEqual(self.score.last_played, now, 'Could not save date')

    def testCanCreateNewObject(self):
        self.score.save()
        object_id = self.score.objectId

        self.assertIsNotNone(object_id, 'Can not create object')
        self.assertIsInstance(object_id, six.string_types)
        self.assertIsInstance(self.score.createdAt, datetime.datetime)
        self.assertTrue(GameScore.Query.filter(objectId=object_id).exists(), 'Can not create object')

    def testCanUpdateExistingObject(self):
        self.sao_paulo.save()
        self.sao_paulo.country = 'Brazil'
        self.sao_paulo.save()
        self.assertIsInstance(self.sao_paulo.updatedAt, datetime.datetime)

        city = City.Query.get(name='São Paulo')
        self.assertEqual(city.country, 'Brazil', 'Could not update object')

    def testCanDeleteExistingObject(self):
        self.score.save()
        object_id = self.score.objectId
        self.score.delete()
        self.assertFalse(GameScore.Query.filter(objectId=object_id).exists(),
                         'Failed to delete object %s on Parse ' % self.score)

    def testCanIncrementField(self):
        previous_score = self.score.score
        self.score.save()
        self.score.increment('score')
        self.assertTrue(GameScore.Query.filter(score=previous_score + 1).exists(),
                     'Failed to increment score on backend')

    def testAssociatedObject(self):
        """test saving and associating a different object"""

        self.collected_item.save()
        self.score.item = self.collected_item
        self.score.save()

        # get the object, see if it has saved
        qs = GameScore.Query.get(objectId=self.score.objectId)
        self.assertIsInstance(qs.item, CollectedItem)
        self.assertEqual(qs.item.type, "Sword", "Associated CollectedItem does not have correct attributes")

    def testBatch(self):
        """test saving, updating and deleting objects in batches"""
        scores = [GameScore(score=s, player_name='Jane', cheat_mode=False) for s in range(5)]
        batcher = ParseBatcher()
        batcher.batch_save(scores)
        self.assertEqual(GameScore.Query.filter(player_name='Jane').count(), 5,
                     "batch_save didn't create objects")
        self.assertTrue(all(s.objectId is not None for s in scores),
                     "batch_save didn't record object IDs")

        # test updating
        for s in scores:
            s.score += 10
        batcher.batch_save(scores)

        updated_scores = GameScore.Query.filter(player_name='Jane')
        self.assertEqual(sorted([s.score for s in updated_scores]),
                         list(range(10, 15)), msg="batch_save didn't update objects")

        # test deletion
        batcher.batch_delete(scores)
        self.assertEqual(GameScore.Query.filter(player_name='Jane').count(), 0,
                     "batch_delete didn't delete objects")


class TestPointer(unittest.TestCase):

    def testToNative(self):
        ptr = Pointer(GameScore(objectId='xyz'))
        self.assertEqual(ptr._to_native(), dict(__type='Pointer', className='GameScore', objectId='xyz'))
        ptr = Pointer(User(objectId='dh56yz', username="dhelmet@spaceballs.com"))
        self.assertEqual(ptr._to_native(), dict(__type='Pointer', className='_User', objectId='dh56yz'))


class TestTypes(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime.now()
        self.score = GameScore(
            score=1337, player_name='John Doe', cheat_mode=False,
            date_of_birth=self.now
        )
        self.sao_paulo = City(
            name='São Paulo', location=GeoPoint(-23.5, -46.6167)
        )

    def testCanConvertToNative(self):
        native_data = self.sao_paulo._to_native()
        self.assertIsInstance(native_data, dict, 'Can not convert object to dict')

    def testCanConvertNestedLocation(self):
        native_sao_paulo = self.sao_paulo._to_native()
        location_dict = native_sao_paulo.get('location')

        self.assertIsInstance(location_dict, dict,
                              'Expected dict after conversion. Got %s' % location_dict)
        self.assertEqual(location_dict.get('latitude'), -23.5,
                         'Can not serialize geopoint data')

    def testCanConvertDate(self):
        native_date = self.score._to_native().get('date_of_birth')
        self.assertIsInstance(native_date, dict,
                              'Could not serialize date into dict')
        iso_date = native_date.get('iso')
        now = '{0}Z'.format(self.now.isoformat()[:-3])
        self.assertEqual(iso_date, now, 'Expected %s. Got %s' % (now, iso_date))


class TestQuery(unittest.TestCase):
    """Tests of an object's Queryset"""

    @classmethod
    def setUpClass(cls):
        """save a bunch of GameScore objects with varying scores"""
        # first delete any that exist
        ParseBatcher().batch_delete(GameScore.Query.all())
        ParseBatcher().batch_delete(Game.Query.all())

        cls.game = Game(title="Candyland", creator=None)
        cls.game.save()

        cls.scores = [GameScore(score=s, player_name='John Doe', game=cls.game) for s in range(1, 6)]
        ParseBatcher().batch_save(cls.scores)

    @classmethod
    def tearDownClass(cls):
        '''delete all GameScore and Game objects'''
        ParseBatcher().batch_delete(chain(cls.scores, [cls.game]))

    def setUp(self):
        self.test_objects = []

    def tearDown(self):
        '''delete additional helper objects created in perticular tests'''
        if self.test_objects:
            ParseBatcher().batch_delete(self.test_objects)
            self.test_objects = []

    def testExists(self):
        """test the Queryset.exists() method"""
        for s in range(1, 6):
            self.assertTrue(GameScore.Query.filter(score=s).exists(),
                            "exists giving false negative")
        self.assertFalse(GameScore.Query.filter(score=10).exists(),
                         "exists giving false positive")

    def testCanFilter(self):
        '''test the Queryset.filter() method'''
        for s in self.scores:
            qobj = GameScore.Query.filter(objectId=s.objectId).get()
            self.assertEqual(qobj.objectId, s.objectId,
                             "Getting object with .filter() failed")
            self.assertEqual(qobj.score, s.score,
                             "Getting object with .filter() failed")

        # test relational query with other Objects
        num_scores = GameScore.Query.filter(game=self.game).count()
        self.assertTrue(num_scores == len(self.scores),
                        "Relational query with .filter() failed")

    def testGetExceptions(self):
        '''test possible exceptions raised by Queryset.get() method'''
        self.assertRaises(query.QueryResourceDoesNotExist,
                          GameScore.Query.filter(score__gt=20).get)
        self.assertRaises(query.QueryResourceMultipleResultsReturned,
                          GameScore.Query.filter(score__gt=3).get)

    def testCanQueryDates(self):
        last_week = datetime.datetime.now() - datetime.timedelta(days=7)
        score = GameScore(name='test', last_played=last_week)
        score.save()
        self.test_objects.append(score)
        self.assertTrue(GameScore.Query.filter(last_played=last_week).exists(), 'Could not run query with dates')


    def testComparisons(self):
        """test comparison operators- gt, gte, lt, lte, ne"""
        scores_gt_3 = GameScore.Query.filter(score__gt=3)
        self.assertEqual(len(scores_gt_3), 2)
        self.assertTrue(all([s.score > 3 for s in scores_gt_3]))

        scores_gte_3 = GameScore.Query.filter(score__gte=3)
        self.assertEqual(len(scores_gte_3), 3)
        self.assertTrue(all([s.score >= 3 for s in scores_gt_3]))

        scores_lt_4 = GameScore.Query.filter(score__lt=4)
        self.assertEqual(len(scores_lt_4), 3)
        self.assertTrue(all([s.score < 4 for s in scores_lt_4]))

        scores_lte_4 = GameScore.Query.filter(score__lte=4)
        self.assertEqual(len(scores_lte_4), 4)
        self.assertTrue(all([s.score <= 4 for s in scores_lte_4]))

        scores_ne_2 = GameScore.Query.filter(score__ne=2)
        self.assertEqual(len(scores_ne_2), 4)
        self.assertTrue(all([s.score != 2 for s in scores_ne_2]))

    def testChaining(self):
        lt_4_gt_2 = GameScore.Query.filter(score__lt=4).filter(score__gt=2)
        self.assertEqual(len(lt_4_gt_2), 1, 'chained lt+gt not working')
        self.assertEqual(lt_4_gt_2[0].score, 3, 'chained lt+gt not working')

        q = GameScore.Query.filter(score__gt=3, score__lt=3)
        self.assertFalse(q.exists(), "chained lt+gt not working")

        # test original queries are idependent after filting
        q_all = GameScore.Query.all()
        q_special = q_all.filter(score__gt=3)
        self.assertEqual(len(q_all), 5)
        self.assertEqual(len(q_special), 2)

        q_all = GameScore.Query.all()
        q_limit = q_all.limit(1)
        self.assertEqual(len(q_all), 5)
        self.assertEqual(len(q_limit), 1)


    def testOrderBy(self):
        """test three options- order, limit, and skip"""
        scores_ordered = GameScore.Query.all().order_by("score")
        self.assertEqual([s.score for s in scores_ordered], [1, 2, 3, 4, 5])

        scores_ordered_desc = GameScore.Query.all().order_by("score", descending=True)
        self.assertEqual([s.score for s in scores_ordered_desc], [5, 4, 3, 2, 1])

    def testLimit(self):
        q = GameScore.Query.all().limit(3)
        self.assertEqual(len(q), 3)

    def testSkip(self):
        q = GameScore.Query.all().skip(3)
        self.assertEqual(len(q), 2)

    def testSelectRelated(self):
        score = GameScore.Query.all().select_related('game').limit(1)[0]
        self.assertTrue(score.game.objectId)
        #nice to have - also check no more then one query is triggered

    def testCanCompareDateInequality(self):
        today = datetime.datetime.today()
        tomorrow = today + datetime.timedelta(days=1)
        self.assertEqual(GameScore.Query.filter(createdAt__lte=tomorrow).count(), 5,
                         'Could not make inequality comparison with dates')

    def testRelations(self):
        """Make some maps, make a Game Mode that has many maps, find all maps
        given a Game Mode"""
        maps = [GameMap(name="map " + i) for i in ['a', 'b', 'c', 'd']]
        ParseBatcher().batch_save(maps)

        gm = GameMode(name='test mode')
        gm.save()
        gm.addRelation("maps", GameMap.__name__, [m.objectId for m in maps])

        modes = GameMode.Query.all()
        self.assertEqual(len(modes), 1)
        mode = modes[0]
        maps_for_mode = GameMap.Query.filter(maps__relatedTo=mode)
        self.assertEqual(len(maps_for_mode), 4)

        gm.delete()
        ParseBatcher().batch_delete(maps)

    def testQueryByRelated(self):
        game_scores_direct = GameScore.Query.filter(game=self.game)
        self.assertTrue(len(game_scores_direct) > 0)

        game_scores_in = GameScore.Query.filter(game__in=[self.game])
        self.assertEqual(len(game_scores_in), len(game_scores_direct))


class TestFunction(unittest.TestCase):
    def setUp(self):
        '''create and deploy cloud functions'''
        original_dir = os.getcwd()

        cloud_function_dir = os.path.join(os.path.split(__file__)[0], 'cloudcode')
        os.chdir(cloud_function_dir)
        if not os.path.exists("config"):
            os.makedirs("config")
        if not os.path.exists("public"):
            os.makedirs("public")
        # write the config file
        with open("config/global.json", "w") as outf:
            outf.write(GLOBAL_JSON_TEXT % (settings_local.APPLICATION_ID,
                                           settings_local.MASTER_KEY))
        try:
            subprocess.call(["parse", "deploy"])
        except OSError as why:
            print("parse command line tool must be installed " \
                "(see https://www.parse.com/docs/cloud_code_guide)")
            self.skipTest(why)
        os.chdir(original_dir)

    def tearDown(self):
        ParseBatcher().batch_delete(Review.Query.all())

    def test_simple_functions(self):
        """test hello world and averageStars functions"""
        # test the hello function- takes no arguments

        hello_world_func = Function("hello")
        ret = hello_world_func()
        self.assertEqual(ret["result"], u"Hello world!")

        # Test the averageStars function- takes simple argument
        r1 = Review(movie="The Matrix", stars=5,
                    comment="Too bad they never made any sequels.")
        r1.save()
        r2 = Review(movie="The Matrix", stars=4, comment="It's OK.")
        r2.save()

        star_func = Function("averageStars")
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
        if User.Query.filter(username=self.username).exists():
            return User.login(self.username, self.password)
        else:
            return self._get_user()

    def setUp(self):
        self.username = TestUser.USERNAME
        self.password = TestUser.PASSWORD
        self.game = None

        try:
            u = User.login(self.USERNAME, self.PASSWORD)
        except ResourceRequestNotFound:
            # if the user doesn't exist, that's fine
            return
        u.delete()

    def tearDown(self):
        self._destroy_user()
        if self.game:
            self.game.delete()
            self.game = None

    def testCanSignUp(self):
        self._destroy_user()
        user = User.signup(self.username, self.password)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.username)

    def testCanLogin(self):
        self._get_user()  # User should be created here.
        user = User.login(self.username, self.password)
        self.assertTrue(user.is_authenticated(), 'Login failed')

    def testCanUpdate(self):
        user = self._get_logged_user()
        phone_number = '555-5555'

        # add phone number and save
        user.phone = phone_number
        user.save()

        self.assertTrue(User.Query.filter(phone=phone_number).exists(),
                     'Failed to update user data. New info not on Parse')

    def testCanBatchUpdate(self):
        user = self._get_logged_user()
        phone_number = "555-0134"

        original_updatedAt = user.updatedAt

        user.phone = phone_number
        batcher = ParseBatcher()
        batcher.batch_save([user])

        self.assertTrue(User.Query.filter(phone=phone_number).exists(),
                        'Failed to batch update user data. New info not on Parse')
        self.assertNotEqual(user.updatedAt, original_updatedAt,
                            'Failed to batch update user data: updatedAt not changed')

    def testUserAsQueryArg(self):
        user = self._get_user()
        g = self.game = Game(title='G1', creator=user)
        g.save()
        self.assertEqual(1, len(Game.Query.filter(creator=user)))

    def testCanGetCurrentUser(self):
        user = User.signup(self.username, self.password)
        self.assertIsNotNone(user.sessionToken)

        register(
            getattr(settings_local, 'APPLICATION_ID'),
            getattr(settings_local, 'REST_API_KEY'),
            session_token=user.sessionToken
        )

        current_user = User.current_user()

        register(
            getattr(settings_local, 'APPLICATION_ID'),
            getattr(settings_local, 'REST_API_KEY'),
            master_key=getattr(settings_local, 'MASTER_KEY')
        )
        
        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.sessionToken, user.sessionToken)
        self.assertEqual(current_user.username, user.username)


class TestPush(unittest.TestCase):
    """
    Test Push functionality. Currently just sends the messages, ensuring they
    don't lead to an error, but does not test whether the messages actually
    went through and with the proper attributes (may be worthwhile to
    set up such a test).
    """
    def testCanMessage(self):
        Push.message("Giants beat the Mets.",
                     channels=["Giants", "Mets"])

        Push.message("Willie Hayes injured by own pop fly.",
                     channels=["Giants"], where={"injuryReports": True})

        Push.message("Giants scored against the A's! It's now 2-2.",
                     channels=["Giants"], where={"scores": True})

    def testCanAlert(self):
        Push.alert({"alert": "The Mets scored! The game is now tied 1-1.",
                    "badge": "Increment", "title": "Mets Score"},
                   channels=["Mets"], where={"scores": True})


def run_tests():
    """Run all tests in the parse_rest package"""
    tests = unittest.TestLoader().loadTestsFromNames(['parse_rest.tests'])
    t = unittest.TextTestRunner(verbosity=1)
    t.run(tests)


if __name__ == "__main__":
    # command line
    unittest.main()
