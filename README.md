# FL-Development
A repository for developing an FL Framework.

## Workplace Setup: *Python*

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
python3 -m pip freeze -l > requirements.txt
```

## Workplace Setup: *Go + MPHE*

If you are getting an error when importing `./mphe/_mphe.so` (in `mphe.py`) then you need to build it yourself using [Go](https://golang.org/doc/install).
```bash
cd ./mphe
go build -buildmode=c-shared -o _mphe.so
```
