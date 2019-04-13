from flask import Flask
from flask import jsonify
from flask import request
import checkdmarc
import os
import uuid

import socket  # gethostbyname
from collections import OrderedDict

app = Flask(__name__)

app.config['DEV'] = os.getenv('FLASK_ENV', 'production') == 'development'


@app.route('/')
def index():
    return '<a href="/lookup/kripos.no">Test kripos.no</a><br />'\
           '<a href="/lookup/async/kripos.no">Test kripos.no async</a><br />'\
           'Development: ' + str(app.config['DEV'])


@app.route('/lookup/async/<domain>')
def lookup_async(domain):
    return jsonify({"error": "not implemented - " + domain}), 500
    #if not domain:
    #    domain = request.args.get("domain")
    #if domain:
    #    return full_check(domain)
    #return jsonify({"error": "missing argument: domain"}), 400


@app.route('/lookup/<domain>')
def lookup(domain):
    if domain and "." in domain:
        return full_check(domain)
    return jsonify({"error": "missing or invalid argument: /lookup/<domain>"}), 400


# We want to skip tls check (port 25 etc traffic) by default when running on Heroku
def full_check(domain, skip_tls=True):
    res = checkdmarc.check_domains([domain], skip_tls=skip_tls)

    output = OrderedDict()
    output['about'] = "For questions: mailto:hildenae+dmarc@gmail.com. Data produced "\
                      "using https://domainaware.github.io/checkdmarc/index.html"
    # We do this to make sure "about" is put first in the merged ordered dict
    output.update(res)

    return jsonify(output), 200
