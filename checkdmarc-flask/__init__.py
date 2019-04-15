from flask import Flask
from flask import jsonify
from flask import render_template
from flask import send_from_directory

# for reading environment variables and creating paths
import os
import signal

from .utils import full_check, force_iso_tz, TimedOutExc
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config/flask.cfg')
    app.config['DEV'] = os.getenv('FLASK_ENV', 'production') == 'development'
    # We want human-readable JSON
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    # WHY would you make escaping unicode the default? WHY?
    app.config['JSON_AS_ASCII'] = False

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def index(path):
        example_domains = app.config['EXAMPLE_DOMAINS']
        test_domains = app.config['TEST_DOMAINS']
        debug_info = {"path": path}
        return render_template(
                                'index.html',
                                example_domains=example_domains,
                                test_domains=test_domains,
                                debug_info=debug_info
                              )

    @app.route('/lookup/async/<domain>')
    def lookup_async(domain):
        import redis
        from rq import Queue

        r = redis.from_url(os.environ.get("REDIS_URL"))
        q = Queue('lookups', connection=r)
        # TODO: Could we use Job.requeue if job has been run before?
        result = q.enqueue(full_check, domain,
                           job_id=domain,
                           result_ttl=300,  # keep results for 5 minutes (300s)
                           failure_ttl=300,   # delete failed jobs
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
        from rq.exceptions import NoSuchJobError

        r = redis.from_url(os.environ.get("REDIS_URL"))
        try:
            job = Job.fetch(job_id[7:], connection=r)
        except NoSuchJobError:
            # TODO: Requeue job here
            return jsonify({
                            "error": "NoSuchJobError",
                            "msg": "Job does not exist. It may have expired (5 minutes) or never existed",
                            "job_id": job_id
                            }), 404
        # print(dir(job))
        if job.is_finished:
            job.result['_lookup_data'] = \
                {
                 'started_at': utils.force_iso_tz(job.started_at),
                 'ended_at': force_iso_tz(job.ended_at)
                }
            return jsonify(job.result), 200

        return jsonify({"job_id": job_id,
                        "status": job.get_status()
                        }), 200

    @app.route('/lookup/<domain>')
    @app.route('/lookup/', defaults={"domain": None})
    def lookup(domain):
        if not domain or "." not in domain:
            return jsonify({
                            "error": "MissingOrInvalidDomain",
                            "msg": "A valid domain must be specified: /lookup/<domain>"
                            }), 400
        started_at = datetime.utcnow()

        result = None
        try:
            result = full_check(domain, timeout=25)
        except TimedOutExc as toe:
            return jsonify({
                            "error": "TimedOutExc",
                            "msg": str(toe),
                            }), 500
        ended_at = datetime.utcnow()
        result['_lookup_data'] = \
            {
                'started_at': utils.force_iso_tz(started_at),
                'ended_at': force_iso_tz(ended_at)
            }
        # print(result)
        return jsonify(result), 200

    @app.route('/favicon.ico')
    def favicon():
        # TODO: Find out why this is not cached by chrome (, cache_timeout=3600)
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')

    # Activate debug for gunicorn
    if app.debug:
        from werkzeug.debug import DebuggedApplication
        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

    return app
