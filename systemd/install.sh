sudo systemctl link $PWD/gunicorn.service
sudo systemctl link $PWD/gunicorn.socket
sudo ln $PWD/gunicorn.conf /etc/tmpfiles.d/gunicorn.conf

sudo systemctl daemon-reload
sudo systemctl enable gunicorn.socket
sudo ln -s $PWD/gunicorn.conf /etc/tmpfiles.d/gunicorn.conf

# sudo /usr/sbin/nginx -t -c /etc/nginx/nginx.conf
