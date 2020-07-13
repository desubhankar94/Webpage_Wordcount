import os
import requests
import operator
import re
import nltk
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from stop_words import stops
from collections import Counter
from bs4 import BeautifulSoup
from rq import Queue
from rq.job import Job
from worker import conn
from flask import jsonify
import functools
from pymemcache.client import base


app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
#app.config['CACHE_TYPE'] = 'simple'
db = SQLAlchemy(app)

q = Queue(connection=conn)
client = base.Client(('localhost', 11211))


from models import *

def count_and_save_words(url):

    errors = []
    results = {}
    raw = ""
    
    print('cache....???', client.get(url))
    
    if client.get(url) != None :
        print("url match found in cache")
        print("skipping db entry as already inserted recently...")
        print(client.get(url))
        result = client.get(url).decode()
        print(result)
        return result
    else :
        print("url match NOT found in cache")
        try:
            r = requests.get(url)
        except:
            errors.append("Unable to get URL. Please make sure it's valid and try again.")
    
        # text processing
        raw = BeautifulSoup(r.text).get_text() 
        nltk.data.path.append('./nltk_data/')  # set the path
        tokens = nltk.word_tokenize(raw)
        text = nltk.Text(tokens)

        # remove punctuation, count raw words
        nonPunct = re.compile('.*[A-Za-z].*')
        raw_words = [w for w in text if nonPunct.match(w)]
        raw_word_count = Counter(raw_words)

        # stop words
        no_stop_words = [w for w in raw_words if w.lower() not in stops]
        no_stop_words_count = Counter(no_stop_words)  
       
    print("BeautifulSoup done...")

    # save the results
    try:
        result = Result(
            url=url,
            result_all=raw_word_count,
            result_no_stop_words=no_stop_words_count
        )
        db.session.add(result)
        db.session.commit()
        client.set(url, result.id, expire=360)
        print(url, 'inserted in cache')
        print(result.id)
        print(type(result.id))
        return result.id     
    except:
        errors.append("Unable to add item to database.")
        return render_template('index.html', errors=errors, results=results)

@app.route('/', methods=['GET', 'POST'])
def index():
    results = {}
    job_id = -1 
    
    if request.method == "POST":
        # this import solves a rq bug which currently exists
        from app import count_and_save_words

        # get url that the person has entered
        url = request.form['url']
        if not url[:8].startswith(('https://', 'http://')):
            url = 'http://' + url
        
        job = q.enqueue_call(
            func=count_and_save_words, args=(url,), result_ttl=360
        )
        print(job.get_id())
        
        job_id = job.get_id()
        return redirect(url_for('get_results', job_key=job_id))          
        
    return render_template('index.html', results=results)
    

@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):

    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        result = Result.query.filter_by(id=job.result).first()
        print(result)
        results = sorted(
            result.result_no_stop_words.items(),
            key=operator.itemgetter(1),
            reverse=True
        )[:10]

        return jsonify(results)
    else:
        return "Nay! Still Processing. Please refresh Again;", 202



if __name__ == '__main__':
    app.run()
