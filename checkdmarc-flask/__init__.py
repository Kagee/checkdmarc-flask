from flask import Flask
from flask import jsonify
from flask import send_from_directory

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
    job_id = result.key.decode("utf-8")
    return jsonify({
                    "enqueued": domain,
                    "job_id": job_id,
                    "url": '/lookup/job/' + job_id
                    }), 200


@app.route('/lookup/job/<job_id>')
def lookup_job(job_id):
    import redis
    from rq.job import Job

    r = redis.from_url(os.environ.get("REDIS_URL"))
    job = Job.fetch(job_id[7:], connection=r)
    return jsonify({"job_id": job_id,
                    # "status": job.status,
                    "dir": dir(job)
                    }), 200


@app.route('/lookup/<domain>')
def lookup(domain):
    if domain and "." in domain:
        res = full_check(domain)
        return jsonify(res[0]), res[1]
    return jsonify({"error": "missing or invalid argument: /lookup/<domain>"}), 400


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


# We want to skip tls check (port 25 etc traffic) by default when running on Heroku
def full_check(domain, skip_tls=True):
    import time
    time.sleep(10)
    res = checkdmarc.check_domains([domain], skip_tls=skip_tls)

    output = OrderedDict()
    output['about'] = "For questions: mailto:hildenae+dmarc@gmail.com. Data produced "\
                      "using https://domainaware.github.io/checkdmarc/index.html"
    # We do this to make sure "about" is put first in the merged ordered dict
    output.update(res)

    return output, 200


if __name__ == '__main__':
    app.run()
