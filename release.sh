rm -rf dist
pip install -e .[release]
python3 -m build
python3 -m twine upload dist/*