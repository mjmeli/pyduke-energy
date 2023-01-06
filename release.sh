rm -rf dist
pip install twine
python3 -m build
python3 -m twine upload dist/*