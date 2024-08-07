web: gunicorn rideTunes.wsgi:application --chdir RideTunes/rideTunes --log-level debug --log-file -
runserver: cd RideTunes/rideTunes && python manage.py runserver 0.0.0.0:$PORT
worker: cd RideTunes/rideTunes && celery -A rideTunes worker --loglevel=info --concurrency=2