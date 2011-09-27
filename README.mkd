ParsePy
=======

**ParsePy** is a Python client for the [Parse REST API](https://www.parse.com/docs/rest). It provides Python object mapping for Parse objects with methods to save, update, and delete objects, as well as an interface for querying stored objects.

Basic Usage
-----------

Let's get everything set up first. You'll need to give **ParsePy** your _Application Id_ and _Master Key_ (available from your Parse dashboard) in order to get access to your data.

~~~~~ {python}
>>> import ParsePy
>>> ParsePy.APPLICATION_ID = "your application id"
>>> ParsePy.MASTER_KEY = "your master key here"
~~~~~

To create a new object of the Parse class _GameScore_:

~~~~~ {python}
>>> gameScore = ParsePy.ParseObject("GameScore")
>>> gameScore.score = 1337
>>> gameScore.playerName = "Sean Plott"
>>> gameScore.cheatMode = False
~~~~~

As you can see, we add new properties simply by assigning values to our _ParseObject_'s attributes. Supported data types are any type that can be serialized by JSON and Python's _datetime.datetime_ object. (Binary data and references to other _ParseObject_'s are also supported, as we'll see in a minute.)

To save our new object, just call the save() method:

~~~~~ {python}
>>> gameScore.save()
~~~~~

If we want to make an update, just call save() again after modifying an attribute to send the changes to the server:

~~~~~ {python}
>>> gameScore.score = 2061
>>> gameScore.save()
~~~~~

Now that we've done all that work creating our first Parse object, let's delete it:

~~~~~ {python}
>>> gameScore.delete()
~~~~~

That's it! You're ready to start saving data on Parse.

Object Metadata
---------------

The methods objectId(), createdAt(), and updatedAt() return metadata about a _ParseObject_ that cannot be modified through the API:

~~~~~ {python}
>>> gameScore.objectId()
'xxwXx9eOec'
>>> gameScore.createdAt()
datetime.datetime(2011, 9, 16, 21, 51, 36, 784000)
>>> gameScore.updatedAt()
datetime.datetime(2011, 9, 118, 14, 18, 23, 152000)
~~~~~

Additional Datatypes
--------------------

If we want to store data in a ParseObject, we should wrap it in a ParseBinaryDataWrapper. The ParseBinaryDataWrapper behaves just like a string, and inherits all of _str_'s methods.

~~~~~ {python}
>>> gameScore.victoryImage = ParsePy.ParseBinaryDataWrapper('\x03\xf3\r\n\xc7\x81\x7fNc ... ')
~~~~~

We can store a reference to another ParseObject by assigning it to an attribute:

~~~~~ {python}
>>> collectedItem = ParsePy.ParseObject("CollectedItem")
>>> collectedItem.type = "Sword"
>>> collectedItem.isAwesome = True
>>> collectedItem.save() # we have to save it before it can be referenced

>>> gameScore.item = collectedItem
~~~~~

Querying
--------

To retrieve an object with a Parse class of _GameScore_ and an _objectId_ of _xxwXx9eOec_, run:

~~~~~ {python}
>>> gameScore = ParsePy.ParseQuery("GameScore").get("xxwXx9eOec")
~~~~~

We can also run more complex queries to retrieve a range of objects. For example, if we want to get a list of _GameScore_ objects with scores between 1000 and 2000 ordered by _playerName_, we would call:

~~~~~ {python}
>>> query = ParsePy.ParseQuery("GameScore")
>>> query = query.gte("score", 1000).lt("score", 2000).order("playerName")
>>> GameScores = query.fetch()
~~~~~

Notice how queries are built by chaining filter functions. The available filter functions are:

* **Less Than**
    * lt(_parameter_name_, _value_)
* **Less Than Or Equal To**
    * lte(_parameter_name_, _value_)
* **Greater Than**
    * gt(_parameter_name_, _value_)
* **Greater Than Or Equal To**
    * gte(_parameter_name_, _value_)
* **Not Equal To**
    * ne(_parameter_name_, _value_)
* **Limit**
    * limit(_count_)
* **Skip**
    * skip(_count_)

We can also order the results using:

* **Order**
    * order(_parameter_name_, _decending_=False)

That's it! This is a first try at a Python library for Parse, and is probably not bug-free. If you run into any issues, please get in touch -- parsepy@paulkastner.com. Thanks!
