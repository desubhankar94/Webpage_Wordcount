import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = 'qwerty'
    ENV = '***'
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']


class ProductionConfig(Config):
    DEBUG = False
    ENV = 'PROD'


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'STG'


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    ENV = 'DEV'


class TestingConfig(Config):
    TESTING = True
    ENV = 'TEST'