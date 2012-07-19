from flask import Flask

app = Flask(__name__)
app.config.update(SECRET_KEY="fhdsjfhsdkjfhsk432853487")

from admin import *
from views import *
