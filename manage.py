from flaskext.script import Manager

from app import app

manager = Manager(app)

@manager.command
def syncdb():

    from models import *
    db.create_all()


if __name__ == "__main__":
    manager.run()
