from flaskext.script import Manager
from flask_evolution import Evolution

from app import app

manager = Manager(app)
evolution = Evolution(app)

@manager.command
def syncdb():
    from models import *
    db.create_all()

@manager.command
def migrate(action):
  	evolution.manager(action)


if __name__ == "__main__":
    manager.run()
