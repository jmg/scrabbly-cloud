from flask import Flask
import os

app = Flask(__name__)

ENV = os.environ.get("ENV", "LOCAL")
DEBUG = True
ENABLE_REAL_TIME = ENV != "PROD"

configs = {
	"PROD": {
		"SECRET_KEY":"522748524ad010358705b6852b81be4c",
		"SQLALCHEMY_DATABASE_URI": os.environ.get('DATABASE_URL',''),
	},
	"LOCAL": {
		"SECRET_KEY":"522748524ad010358705b6852b81be4c",
		"SQLALCHEMY_DATABASE_URI":"sqlite:////%s/base.sqlite" % os.getcwd(),
	}
}
app.config.update(configs[ENV])

from admin import *
from views import *

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	app.run(host='0.0.0.0', port=port, debug=DEBUG)
