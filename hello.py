from flask import Flask
from flask import jsonify

import checkdmarc

import os

from collections import OrderedDict

app = Flask(__name__)

app.config['DEV'] = os.getenv('FLASK_ENV', 'production') == 'development'
# We want human-readable JSON
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

@app.route('/')
def index():
    return '<a href="/lookup/kripos.no">Test kripos.no</a><br />'\
           '<a href="/lookup/async/kripos.no">Test kripos.no async</a><br />'\
           'Development: ' + str(app.config['DEV'])


@app.route('/lookup/async/<domain>')
def lookup_async(domain):
    import redis
    from rq import Queue

    r = redis.from_url(os.environ.get("REDIS_URL"))
    q = Queue('lookups', connection=r)
    result = q.enqueue(full_check, domain,
                       result_ttl=300,  # keep results for 5 minutes (300s)
                       failure_ttl=0,   # delete failed jobs
                       ttl=60,          # discard job if not started within 1 min (60s)
                       job_timeout=30   # fail job if it takes more than 30s
                       )
    return jsonify({"enqueued": domain, "result": str(result)}), 200


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


if __name__ == '__main__':
    app.run()
