"""
Contains unit tests for the Python Parse REST API wrapper
"""

import os
import subprocess
import unittest
import urllib2
import datetime

import __init__ as parse_rest

try:
    import settings_local
except ImportError:
    raise ImportError('You must create a settings_local.py file with an ' +
                      'APPLICATION_ID, REST_API_KEY, and a MASTER_KEY ' +
                      'to run tests.')

parse_rest.APPLICATION_ID = settings_local.APPLICATION_ID
parse_rest.REST_API_KEY = settings_local.REST_API_KEY


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


### FUNCTIONS ###
def test_obj(saved=False):
    """Return a test parse_rest.Object (content is from the docs)"""
    ret = parse_rest.Object("GameScore")
    ret.score = 1337
    ret.playerName = "Sean Plott"
    ret.cheatMode = False
    ret.location = "POINT(-30.0 43.21)"  # "POINT(30 -43.21)"
    if saved:
        ret.save()
    return ret


### CLASSES ###
class TestObjectAndQuery(unittest.TestCase):
    """
    Tests for the parse_rest.Object interface for creating and updating Parse
    objects, as well as the parse_rest.ObjectQuery interface for retrieving
    them
    """

    def check_test_obj(self, o):
        """check that the object is consistent with the test object"""
        self.assertEqual(o.objectId().__class__, unicode)
        self.assertEqual(o.updatedAt().__class__, datetime.datetime)
        self.assertEqual(o.createdAt().__class__, datetime.datetime)
        self.assertEqual(o.score, 1337)
        # TODO: str vs unicode
        #self.assertEqual(o.playerName.__class__, unicode)
        self.assertEqual(o.cheatMode.__class__, bool)
        self.assertEqual(o.location, "POINT(-30.0 43.21)")

    def test_object(self):
        """Test the creation, retrieval and updating of a Object"""
        gameScore = test_obj()
        gameScore.save()
        self.check_test_obj(gameScore)

        # retrieve a new one
        query = parse_rest.ObjectQuery('GameScore')
        obj1 = query.get(gameScore.objectId())
        self.check_test_obj(obj1)

        # now update it
        current_updated = obj1.updatedAt()
        obj1.score = 1000
        obj1.save()
        self.assertGreater(obj1.updatedAt(), current_updated)
        self.assertEqual(obj1.score, 1000)

        # test accessing like a dictionary
        self.assertTrue("playerName" in obj1)
        self.assertTrue("score" in obj1)
        self.assertEqual(obj1["score"], 1000)
        self.assertEqual(obj1["playerName"], "Sean Plott")
        obj1["playerName"] = "Sean Scott"
        self.assertEqual(obj1.playerName, "Sean Scott")
        # non-existent or forbidden lookup
        self.assertRaises(KeyError, obj1.__getitem__, "nosuchkey")
        self.assertRaises(KeyError, obj1.__getitem__, "_class_name")

        # re-retrieve it
        obj2 = query.get(obj1.objectId())
        self.assertEqual(obj2.score, 1000)

        # change one object, check that others can be refreshed
        obj2.score = 2000
        obj2.save()

        self.assertEqual(obj1.score, 1000)
        obj1.refresh()
        self.assertEqual(obj1.score, 2000)

        # try removing a field
        obj2.remove("score")
        obj2.save()
        self.assertEqual(obj2.has("score"), False)

    def test_increment(self):
        """Test incrementation of fields"""
        o = test_obj(True)
        self.check_test_obj(o)
        o.save()

        o.increment("score")
        self.assertEqual(o.score, 1338)

        query = parse_rest.ObjectQuery("GameScore")
        o2 = query.get(o.objectId())
        self.assertEqual(o2.score, 1338)

        # one more time
        o.increment("score")
        self.assertEqual(o.score, 1339)
        o3 = query.get(o.objectId())
        self.assertEqual(o3.score, 1339)

    def test_relationship(self):
        """Test relationship between objects"""
        post = parse_rest.Object("Post")
        post.title = "I'm Hungry"
        post.content = "Where should we go for lunch?"
        post.save()

        comment = parse_rest.Object("Comment")
        comment.content = "Let's do Sushirrito"
        comment.parent = post
        comment.save()

        # that should have saved both post and comment
        post_id = post.objectId()
        comment_id = comment.objectId()
        self.assertEqual(post_id.__class__, unicode)
        self.assertEqual(comment_id.__class__, unicode)

        # retrieve new ones
        post2 = parse_rest.ObjectQuery("Post").get(post_id)
        comment2 = parse_rest.ObjectQuery("Comment").get(comment_id)
        # check the relationship between the saved post and comment
        self.assertEqual(comment2.parent.objectId(), post_id)
        self.assertEqual(comment2.parent.title, "I'm Hungry")

    def test_delete(self):
        """Test deleting an object"""
        o = test_obj(True)
        obj_id = o.objectId()
        self.check_test_obj(o)
        o2 = parse_rest.ObjectQuery("GameScore").get(obj_id)
        self.check_test_obj(o2)
        o2.delete()
        self.assertRaises(urllib2.HTTPError,
                          parse_rest.ObjectQuery("GameScore").get, obj_id)


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

        # remove all existing Review objects
        for review in parse_rest.ObjectQuery("Review").fetch():
            review.delete()

    def test_simple_functions(self):
        """test hello world and averageStars functions"""
        # test the hello function- takes no arguments
        hello_world_func = parse_rest.Function("hello")
        ret = hello_world_func()
        self.assertEqual(ret["result"], u"Hello world!")

        # Test the averageStars function- takes simple argument
        r1 = parse_rest.Object("Review", {"movie": "The Matrix",
                                          "stars": 5,
                            "comment": "Too bad they never made any sequels."})
        r1.save()
        r2 = parse_rest.Object("Review", {"movie": "The Matrix",
                                          "stars": 4,
                            "comment": "It's OK."})
        r2.save()

        star_func = parse_rest.Function("averageStars")
        ret = star_func(movie="The Matrix")
        self.assertAlmostEqual(ret["result"], 4.5)


class TestUser(unittest.TestCase):
    def setUp(self):
        """remove the test user if he exists"""
        u = parse_rest.User("dhelmet@spaceballs.com", "12345")
        try:
            u.login()
            u.delete()
        except parse_rest.ParseError as e:
            # if the user doesn't exist, that's fine
            if e.message != "Invalid login":
                raise

    def test_user(self):
        """Test the ability to sign up, log in, and delete users"""
        u = parse_rest.User("dhelmet@spaceballs.com", "12345")
        u.signup()

        # can't save or delete until it's logged in
        self.assertRaises(parse_rest.ParseError, u.save, ())
        self.assertRaises(parse_rest.ParseError, u.delete, ())

        u.login()
        self.assertTrue(hasattr(u, "sessionToken"))
        self.assertNotEqual(u.sessionToken, None)

        # add phone number and save
        u.phone = "555-5555"
        u.save()

        uq = parse_rest.UserQuery()
        u_retrieved = uq.get(u.objectId())
        self.assertEqual(u.username, u_retrieved.username)
        self.assertEqual(u_retrieved.phone, "555-5555")

        # test UserQuery.fetch
        queried_users = uq.fetch()
        self.assertTrue(u.username in [qu.username for qu in queried_users])

        # test accessing like a dictionary
        self.assertEqual(u_retrieved["username"], "dhelmet@spaceballs.com")
        self.assertEqual(u_retrieved["phone"], "555-5555")

        # try creating another account with the same user
        u2 = parse_rest.User("dhelmet@spaceballs.com", "12345")
        self.assertRaises(parse_rest.ParseError, u2.signup)

        # time to delete
        u.delete()


if __name__ == "__main__":
    # command line
    unittest.main()
