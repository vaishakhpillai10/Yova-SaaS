# Quick Start - Asset Register Proper Update

Open Command Prompt in this folder, then run:

```bat
py -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
py manage.py makemigrations
py manage.py migrate
py manage.py seed_demo_data
py manage.py test
```

Then import the real Excel data:

```bat
py manage.py import_real_engineering_data --dry-run
py manage.py import_real_engineering_data
```

Start the server:

```bat
py manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Login:

```text
admin / Admin@12345
```

The real Excel files are already included inside:

```text
data_imports\Engg.xlsx
data_imports\Asset Disposal Form (1).xlsx
```

Test the Asset Register using:

```text
docs\ASSET_REGISTER_TESTING_FLOW.md
```
