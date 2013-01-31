from distutils.core import setup, Command
from unittest import TextTestRunner, TestLoader


class TestCommand(Command):
    """Run test suite using 'python setup.py test'"""
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """Run test suite in parse_rest.tests"""
        from parse_rest import tests
        tests = TestLoader().loadTestsFromNames(["parse_rest.tests"])
        t = TextTestRunner(verbosity=1)
        t.run(tests)


setup(
    name='parse_rest',
    version='0.7.2013',
    description='A client library for Parse.com\'.s REST API',
    url='https://github.com/dgrtwo/ParsePy',
    packages=['parse_rest'],
    maintainer="David Robinson",
    maintainer_email="dgrtwo@princeton.edu",
    cmdclass={"test": TestCommand},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python'
        ]
    )
