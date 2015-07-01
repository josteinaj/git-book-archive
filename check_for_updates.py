#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import json
from dateutil import parser
from datetime import datetime, timedelta
from pprint import pprint
from subprocess import call

def main():
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    archive_dir = parent_dir+"/master-archive"
    json_dir = parent_dir+"/json-database"
    
    if (not os.path.isdir(json_dir)):
        print ("Creating JSON database folder: "+json_dir)
        os.mkdir(json_dir)
    
    for book_id in os.listdir(archive_dir):
        book_dir = archive_dir+"/"+book_id
        if (os.path.isdir(book_dir) and re.match("^\d+$", book_id)):
            print ("Processing book: "+book_id)
            json_filename = json_dir+"/"+book_id+".json"
            
            data = load_data(json_filename)
            data["id"] = book_id
            
            last_modified = None
            for root, dirs, files in os.walk(book_dir):
                for name in files:
                    modified = modification_date(os.path.join(root, name))
                    if (last_modified == None or modified > last_modified):
                        last_modified = modified
                for name in dirs:
                    modified = modification_date(os.path.join(root, name))
                    if (last_modified == None or modified > last_modified):
                        last_modified = modified
            print (book_id+" was last modified: "+str(last_modified))
            
            previous_modified = None
            if ("last_modified" in data):
                previous_modified = parser.parse(data["last_modified"])
            else:
                previous_modified = date.utcnow() - timedelta(days=1)
            
            if (True or last_modified > previous_modified and last_modified > date.utcnow() - timedelta(seconds=60)):
                # the last modified timestamp for the book has changed
                print ("A change has occured in "+book_id)
                call(["git", "add", book_dir])
                
                data["last_modified"] = str(last_modified)
            
            save_data(json_filename, data)


def load_data(json_filename):
    if (not os.path.isfile(json_filename)):
        print ("Creating "+json_filename)
        with open(json_filename, 'w') as json_file:
            json.dump({}, json_file)
    
    try:
        with open(json_filename) as json_file:    
            data = json.load(json_file)
    except Exception as e:
        print ("Warning: Could not read JSON: "+json_filename)
        data = {}
    
    return data


def save_data(json_filename, data):
    with open(json_filename, 'w') as json_file:
        json.dump(data, json_file)


def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.utcfromtimestamp(t)


if __name__ == "__main__":
    main()
