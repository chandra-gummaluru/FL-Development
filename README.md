# FL-Development
A repository for developing an FL Framework.

## Workplace Setup

Install [vitrualenv](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/):
```bash
python3 -m pip install virtualenv
```

Create a virtual environment:
```bash
python3 -m venv venv

# Activate virutal environment
source ./venv/bin/activate
```

Install required modules
```bash
python3 -m pip install -r requirements.txt
```
> To add new Python dependencies run:
```bash
python3 -m pip freeze > requirements.txt
```