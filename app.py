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
import redis
from datetime import timedelta
from time import sleep


app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

q = Queue(connection=conn)
rcache = redis.Redis()

from models import *

def count_and_save_words(url):

    errors = []
    results = {}
    raw = ""
    
    print('cache....???', rcache.get(url))
    
    if rcache.get(url) != None :
        print("url match found in cache")
        print("skipping db entry as already inserted recently...")
        print(rcache.get(url))
        result = rcache.get(url).decode()
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
        rcache.setex(url, 3000, result.id)
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
            func=count_and_save_words, args=(url,), result_ttl=3000
        )
        print(job.get_id())
        
        job_id = job.get_id()

        while not job.is_finished :
            sleep( 1/1000 )

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
    
        return render_template('results.html', results=results)
        #return jsonify(results)
    else:
        #return redirect(url_for('get_results', job_key=job_key))
        return "Nay! Still Processing. Please refresh Again;", 202



if __name__ == '__main__':
    app.run()
