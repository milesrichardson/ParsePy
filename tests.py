"""
Contains unit tests for the Python Parse REST API wrapper
"""

import unittest
import urllib2
import datetime

import __init__ as ParsePy

try:
    import settings_local
except ImportError:
    raise ImportError("You must create a settings_local.py file " +
                      "with an example application to run tests")

ParsePy.APPLICATION_ID = settings_local.APPLICATION_ID
ParsePy.REST_API_KEY = settings_local.REST_API_KEY


### FUNCTIONS ###

def test_obj(saved=False):
    """Return a test ParsePy.ParseObject (content is from the docs)"""
    ret = ParsePy.ParseObject("GameScore")
    ret.score = 1337
    ret.playerName = "Sean Plott"
    ret.cheatMode = False
    ret.location = "POINT(-30.0 43.21)"  # "POINT(30 -43.21)"
    if saved:
        ret.save()
    return ret


### CLASSES ###

class TestParseObjectAndQuery(unittest.TestCase):
    """
    Tests for the ParsePy.ParseObject interface for creating and updating Parse
    objects, as well as the ParsePy.ParseQuery interface for retrieving them
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
        """Test the creation, retrieval and updating of a ParseObject"""
        gameScore = test_obj()
        gameScore.save()
        self.check_test_obj(gameScore)

        # retrieve a new one
        query = ParsePy.ParseQuery("GameScore")
        obj1 = query.get(gameScore.objectId())
        self.check_test_obj(obj1)

        # now update it
        current_updated = obj1.updatedAt()
        obj1.score = 1000
        obj1.save()
        self.assertGreater(obj1.updatedAt(), current_updated)
        self.assertEqual(obj1.score, 1000)

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

        query = ParsePy.ParseQuery("GameScore")
        o2 = query.get(o.objectId())
        self.assertEqual(o2.score, 1338)

        # one more time
        o.increment("score")
        self.assertEqual(o.score, 1339)
        o3 = query.get(o.objectId())
        self.assertEqual(o3.score, 1339)

    def test_relationship(self):
        """Test relationship between objects"""
        post = ParsePy.ParseObject("Post")
        post.title = "I'm Hungry"
        post.content = "Where should we go for lunch?"
        post.save()

        comment = ParsePy.ParseObject("Comment")
        comment.content = "Let's do Sushirrito"
        comment.parent = post
        comment.save()

        # that should have saved both post and comment
        post_id = post.objectId()
        comment_id = comment.objectId()
        self.assertEqual(post_id.__class__, unicode)
        self.assertEqual(comment_id.__class__, unicode)

        # retrieve new ones
        post2 = ParsePy.ParseQuery("Post").get(post_id)
        comment2 = ParsePy.ParseQuery("Comment").get(comment_id)
        # check the relationship between the saved post and comment
        self.assertEqual(comment2.parent.objectId(), post_id)
        self.assertEqual(comment2.parent.title, "I'm Hungry")

    def test_delete(self):
        """Test deleting an object"""
        o = test_obj(True)
        obj_id = o.objectId()
        self.check_test_obj(o)
        o2 = ParsePy.ParseQuery("GameScore").get(obj_id)
        self.check_test_obj(o2)
        o2.delete()
        self.assertRaises(urllib2.HTTPError,
                            ParsePy.ParseQuery("GameScore").get, obj_id)


if __name__ == "__main__":
    # command line
    unittest.main()
