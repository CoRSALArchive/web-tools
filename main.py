from flask import Flask

app = Flask('diffmark')

import scrabble
app.register_blueprint(scrabble.app, url_prefix='/scrabble')

import tsv2lift
app.register_blueprint(tsv2lift.app, url_prefix='/tsv2lift')

import flex2tex
app.register_blueprint(flex2tex.app, url_prefix='/flex2tex')

import query
app.register_blueprint(query.app, url_prefix='/')
