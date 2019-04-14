# web: gunicorn hello:app
# worker: python worker.py
# Hobby, but don't want to pay for an extra dyno to run a simple worker
# https://help.heroku.com/CTFS2TJK/how-do-i-run-multiple-processes-on-a-dyno
web: python app/worker.py & gunicorn app & wait -n
