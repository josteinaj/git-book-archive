#!/usr/bin/python
# -*- coding: utf-8 -*-

import getopt
import sys
import os
import re
import json
import tempfile
from dateutil import parser
from datetime import datetime, timedelta
from pprint import pprint
from subprocess import call

def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hg:a:", ["help", "git-clone=", "archive="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    
    test = True
    if (test == True):
        opts, args = init_test()
    
    archive_dir = None
    git_remote = None
        
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-a", "--archive"):
            archive_dir = arg
        elif opt in ("-g", "--git-clone"):
            git_remote = arg
        else:
            assert False, "Unknown option: "+opt
    
    assert archive_dir != None, "Archive directory must be defined; please specify using --archive"
    archive_dir = os.path.normpath(archive_dir)
    
    if git_remote != None:
        # Initialize archive
        print("Will attempt to clone archive.")
        print("Note that if it runs for more than an hour this process will time out and fail.")
        print("You can clone the repository manually if the timeout is a problem.")
        call(["git", "clone", git_remote, os.path.dirname(archive_dir)], cwd=os.path.dirname(archive_dir), timeout=3600)
        
    else:
        # Check for updates
        assert os.path.exists(archive_dir), "Archive must exist: "+archive_dir+" (use --git-clone if you're trying to initialize an archive)"
        assert os.path.isdir(archive_dir), "Archive must be a directory: "+archive_dir
        
        db_dir = os.path.join(archive_dir, ".db")
        
        if (not os.path.isdir(db_dir)):
            print ("Creating JSON database folder: "+db_dir)
            os.mkdir(db_dir, mode=0o755)
        
        for book_id in os.listdir(archive_dir):
            book_dir = archive_dir+"/"+book_id
            if (os.path.isdir(book_dir) and re.match("^\d+$", book_id)):
                print ("Processing book: "+book_id)
                db_filename = db_dir+"/"+book_id+".json"
                db = load_data(db_filename)
                
                if (test == True):
                    # modify a file for testing purposes
                    testfile = open(os.path.join(book_dir, "file.txt"), "a")
                    testfile.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
                    testfile.close()
                
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
                if ("last_modified" in db):
                    previous_modified = parser.parse(db["last_modified"])
                else:
                    previous_modified = datetime.utcnow() - timedelta(days=1)
                
                if (last_modified > previous_modified and last_modified > datetime.utcnow() - timedelta(seconds=60)):
                    # the last modified timestamp for the book has changed
                    print ("A change has occured in "+book_id)
                    assert 0 == call(["git", "reset"], cwd=archive_dir, timeout=60)
                    assert 0 == call(["git", "add", os.path.relpath(book_dir, archive_dir)], cwd=archive_dir, timeout=60)
                    assert 0 == call(["git", "commit", "-m", "Updated book: "+book_id], cwd=archive_dir, timeout=60)
                    assert 0 == call(["git", "push"], cwd=archive_dir, timeout=60)
                    
                    db["last_modified"] = str(last_modified)
                
                db["id"] = book_id
                save_data(db_filename, db)


def load_data(db_filename):
    if (not os.path.isfile(db_filename)):
        print ("Creating "+db_filename)
        with open(db_filename, 'w') as json_file:
            json.dump({}, json_file)
    
    try:
        with open(db_filename) as json_file:
            data = json.load(json_file)
    except Exception as e:
        print ("Warning: Could not read JSON: "+db_filename)
        data = {}
    
    return data


def save_data(db_filename, data):
    with open(db_filename, 'w') as json_file:
        json.dump(data, json_file)


def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.utcfromtimestamp(t)


def init_test():
    args = []
    tmp_parent = tempfile.gettempdir()
    tmp_remote = os.path.join(tmp_parent, "archive-remote")
    tmp_local = os.path.join(tmp_parent, "archive-local")
    assert os.path.isdir(tmp_remote) or not os.path.exists(tmp_remote) and os.path.isdir(tmp_parent), "Unable to create temporary remote: " + tmp_remote
    assert os.path.isdir(tmp_local) or not os.path.exists(tmp_local) and os.path.isdir(tmp_parent), "Unable to create temporary local: " + tmp_local
    opts = [
        ("-a", tmp_local)
    ]
    if not os.path.exists(tmp_remote):
        os.mkdir(tmp_remote, mode=0o755)
        assert 0 == call(["git", "init", "--bare"], cwd=tmp_remote, timeout=5)
    if not os.path.exists(tmp_local):
        assert 0 == call(["git", "clone", tmp_remote, tmp_local], cwd=tmp_parent, timeout=5)
        
        print("Checking if cloned repository is empty (will give 'fatal: ambigous argument' error if empty)...")
        empty_repo = call(["git", "rev-parse", "HEAD"], cwd=tmp_local, timeout=5)
        if empty_repo:
            print("Initializing test repository")
            
            os.makedirs(os.path.join(tmp_local, "001", "subdir", "subsubdir"), mode=0o755)
            testfile = open(os.path.join(tmp_local, "001", "subdir", "subsubdir", "file001.txt"), "a")
            testfile.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
            testfile.close()
            os.makedirs(os.path.join(tmp_local, "002", "subdir"), mode=0o755)
            testfile = open(os.path.join(tmp_local, "002", "subdir", "file002.txt"), "a")
            testfile.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
            testfile.close()
            
            assert 0 == call(["git", "add", "-A"], cwd=tmp_local, timeout=5)
            assert 0 == call(["git", "commit", "-m", "initialized test repository"], cwd=tmp_local, timeout=5)
            assert 0 == call(["git", "push"], cwd=tmp_local, timeout=5)
        else:
            print("repository is not empty, got: "+empty_repo)

    
    return opts, args


if __name__ == "__main__":
    main(sys.argv[1:])
