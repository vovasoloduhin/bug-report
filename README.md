# Bugtracker 

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts teams bugs
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
 
