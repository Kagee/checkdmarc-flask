from flask import Flask
from flask import jsonify
from flask import render_template
from flask import send_from_directory

from flask_babel import Babel
from flask import request, session, redirect, url_for

# for reading environment variables and creating paths
import os
from uuid import uuid4
from .utils import full_check, force_iso_tz, TimedOutExc
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('config/flask.cfg')

    # We are currently only saving lang in session
    app.secret_key = 'TODO: replace super secret key'

    app.config['DEV'] = os.getenv('FLASK_ENV', 'production') == 'development'

    babel = Babel(app)

    # We want human-readable JSON
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    # WHY would you make escaping unicode the default? WHY?
    app.config['JSON_AS_ASCII'] = False

    @babel.localeselector
    def get_locale():
        if request.args.get('lang'):
            session['lang'] = request.args.get('lang')
        if session.get('lang') in app.config['LANGUAGES'].keys():
            return session.get('lang')
        session.pop('lang', None)
        return request.accept_languages.best_match(app.config['LANGUAGES'].keys())

    @app.route('/backend-test', defaults={'path': ''})
    @app.route('/backend-test/<path:path>')
    def index(path):
        example_domains = app.config['EXAMPLE_DOMAINS']
        test_domains = app.config['TEST_DOMAINS']
        debug_data = {"path": path, "locale": get_locale()}
        return render_template(
                                'backend.html',
                                example_domains=example_domains,
                                test_domains=test_domains,
                                debug_data=debug_data
                              )

    @app.route('/')
    @app.route('/landing')
    def landing():
        return render_template('landing.html', queue_url=url_for('queue'))

    @app.route('/queue')
    def queue():
        domain = request.args.get('domain')
        if not domain:
            return redirect(url_for('landing'))
        job_id = lookup_async(domain, json=False)
        return redirect(url_for('lookup', job_id=job_id))

    @app.route('/lookup')
    def lookup():
        job_id = request.args.get('job_id')
        # total = request.args.get('total_time')
        if not job_id:
            return redirect(url_for('landing'))
        finished, failed, job = return_job(job_id)
        # print(failed)
        if failed:
            # print(dir(result))
            reason = 'Unknown. <br /><br />Please send an e-mail to ' \
                     '<a href="mailto:hildenae+sjekk,email@gmail.com">hildenae+sjekk,email@gmail.com</a> ' \
                     'and with reference ' + job_id
            if "rq.timeouts.JobTimeoutException" in job.exc_info:
                reason = "The lookup timed out. This may be a problem with very slow DNS servers."\
                         "<br /><br />Reference: " + job_id
            return render_template('result-fail.html', reason=reason, job_id=job_id)
        if finished:
            return redirect(url_for('result', job_id=job_id))
        return render_template('working.html', reload=5, status=job.get_status())

    @app.route('/result')
    def result():
        job_id = request.args.get('job_id')
        if not job_id:
            return redirect(url_for('landing'))
        _, _, job = return_job(job_id)
        return render_template('result.html', job_id=job_id, result=job.result)

    @app.route('/lookup/async/<domain>')
    def lookup_async(domain, json=True):
        import redis
        from rq import Queue

        r = redis.from_url(os.environ.get("REDIS_URL"))
        q = Queue('lookups', connection=r)
        job_id = str(uuid4())
        # TODO: Could we use Job.requeue if job has been run before?
        job = q.enqueue(full_check, domain,
                        job_id=job_id,
                        result_ttl=60*60*24*7,   # keep results for 7 days
                        failure_ttl=60*60*24*7,  # delete failed jobs after 30 minutes
                        ttl=120,                 # discard job if not started within 1 min (60s)
                        job_timeout=60           # fail job if it takes more than 30s
                        )
        job_key = job.key.decode("utf-8")
        if json:
            return jsonify({
                        "enqueued": domain,
                        "job_id": job_id,
                        "job_key": job_key,
                        "url": '/lookup/job/' + job_id
                        }), 200
        else:
            return job_id

    def return_job(job_id):
        import redis
        from rq.job import Job

        r = redis.from_url(os.environ.get("REDIS_URL"))
        if job_id.startswith("rq:job:"):
            job_id = job_id[7:]
        job = Job.fetch(job_id, connection=r)
        if job.is_failed:
            registry = job.failed_job_registry
            print(dir(registry))

            return False, job.is_failed, job
        if not job.is_finished:
            return False, job.is_failed, job
        job.result['_lookup_data'] = \
            {
                'started_at': force_iso_tz(job.started_at),
                'ended_at': force_iso_tz(job.ended_at)
            }
        return job, False, job

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

    @app.route('/lookup/json/<domain>')
    @app.route('/lookup/json/', defaults={"domain": None})
    def lookup_json(domain):
        if not domain or "." not in domain:
            return jsonify({
                            "error": "MissingOrInvalidDomain",
                            "msg": "A valid domain must be specified: /lookup/<domain>"
                            }), 400
        started_at = datetime.utcnow()

        # result = None
        try:
            job = full_check(domain, timeout=25)
        except TimedOutExc as toe:
            return jsonify({
                            "error": "TimedOutExc",
                            "msg": str(toe),
                            }), 500
        ended_at = datetime.utcnow()
        job['_lookup_data'] = \
            {
                'started_at': utils.force_iso_tz(started_at),
                'ended_at': force_iso_tz(ended_at)
            }
        # print(result)
        return jsonify(job), 200

    # @app.route('/static/lookup_async_html/<path:path>')
    # def serve_static(path):
    #    templates = [
    #        "landing.html",
    #        "working.html",
    #        "result-good.html",
    #        "result-warn.html",
    #        "result-error.html",
    #        "result-fail.html",
    #        "result-nxdomain.html",
    #    ]
    #    if path in templates:
    #        return render_template(path, render_test_links=True)
    #    return send_from_directory('static/lookup_async_html', path)

    @app.route('/favicon.ico')
    def favicon():
        # TODO: Find out why this is not cached by chrome (, cache_timeout=3600)
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')

    @app.route('/.well-known/<path:filename>')
    def well_known(filename):
        return send_from_directory(app.static_folder + '/well-known/', filename)

    # Activate debug for gunicorn
    if app.debug:
        from werkzeug.debug import DebuggedApplication
        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

    return app
