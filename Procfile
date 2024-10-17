web: daphne -u /tmp/daphne.sock --fd 0 --access-log - --proxy-headers --chdir RideTunes/rideTunes rideTunes.asgi:application
runserver: cd RideTunes/rideTunes && python manage.py runserver 0.0.0.0:$PORT
worker: cd RideTunes/rideTunes && celery -A rideTunes worker --loglevel=info