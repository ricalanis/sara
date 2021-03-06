# -*- coding: utf-8 -*-
# Celery tasks

import os
from celery import Celery
from sklearn.externals import joblib
from profanity_filter import *
import requests
import json

REDIS_HOST = os.getenv( 'REDIS_PORT_6379_TCP_ADDR', 'localhost' )+':'+os.getenv( 'REDIS_PORT_6379_TCP_PORT', '6379' )
BROKER_URL = 'redis://'+ REDIS_HOST +'/0'
CELERY_RESULT_BACKEND = 'redis://'+ REDIS_HOST +'/0'
BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 1800}  # 1/2 hour.

app = Celery('tasks', backend=CELERY_RESULT_BACKEND, broker=BROKER_URL)


@app.task
def evaluate_petition(petition_id, features):
    try:
        pipe = joblib.load('models/bow_ng6_nf9500_ne750.pkl')
        test_data_features = pipe.named_steps['vectorizer'].transform(features)
        test_data_features = test_data_features.toarray()
        # TODO: check API of this method, what's returning on error?
        result = pipe.named_steps['forest'].predict(test_data_features)
        agency = result[0] if len(result) > 0 else -1
    except:
        print "Unexpected error:", sys.exc_info()[0]
        agency = -1
    else:
        return {
            'id': petition_id,
            'agency': agency
        }


@app.task
def catch_bad_words_in_text(text):
    f = ProfanitiesFilter(my_list, replacements="-")
    # TODO: check API of this method, what's returning on error?
    profanity_score = f.profanity_score(text)
    return {
        'text': text,
        'profanity_score': profanity_score
    }


@app.task
def update_remote_petition(results):
    classified_petition = results[0]
    inspected_text = results[1]
    if inspected_text['profanity_score'] > 0:
        proceeds = {u'value': False, u'reason': u'Petición Irrespetuosa'}
    else:
        proceeds = {u'value': True}

    petition = {
        u'id': classified_petition['id'],
        u'text': inspected_text['text'],
        u'agency': classified_petition['agency'],
        u'proceeds': proceeds
    }

    url = os.environ['PETITIONS_SERVER_URL']
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    try:
        r = requests.put(url, data=json.dumps(petition), headers=headers)
        print 'Updating:'
        print json.dumps(petition, encoding='utf-8', ensure_ascii=False)
        print 'PUT request to', url, ' was ', r.status_code
        r.raise_for_status() # Rise an exception if status code is not 200
    except requests.HTTPError as e: 
        print 'HTTP ERROR occured, status code %s' % e.response.status_code
        print 'ERROR reason: %s'  % e.response.reason
        print e
    except requests.exceptions.RequestException as e: # Catch all non HTTP errors
        # example: ConnectionError, URLRequired, TooManyRedirects, ConnectTimeout,
        # ReadTimeout
        print 'An unexpected error ocurred.' 
        print e 

