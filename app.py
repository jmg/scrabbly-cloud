from juggernaut import Juggernaut

from flask import Flask, render_template
app = Flask(__name__)


@app.route("/", methods=['GET'])
def index():

    return render_template('index.html')


@app.route("/send_message", methods=['POST'])
def send_message():

    jug = Juggernaut()
    jug.publish('channel', 'Juggernaut Test')

    return "ok"


if __name__ == '__main__':
    app.run()


