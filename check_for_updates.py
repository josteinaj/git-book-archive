#!/usr/bin/python
# -*- coding: utf-8 -*-

from urllib.parse import urlparse
import argparse
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
    if '--run-tests' in sys.argv:
        run_tests()
    else:
        parser = argparse.ArgumentParser(description="Monitors a book archive and commits changes to git.")
        subparsers = parser.add_subparsers(title='subcommands', metavar="")
        
        parser_update = subparsers.add_parser("update", help="Check archive for changes.")
        parser_update.add_argument("archive", help="Path to the archive.", metavar="PATH")
        parser_update.set_defaults(func=update)
        
        parser_init = subparsers.add_parser("git-init", help="Initialize archive from remote git repository.")
        parser_init.add_argument("archive", help="Path to the archive.", metavar="PATH")
        parser_init.add_argument("git-clone", help="Initialize the archive from this git repository.", metavar="URL")
        parser_init.set_defaults(func=git_init)
        
        group_test = parser.add_argument_group()
        args = parser.parse_args()
    

def git_init(args):
    args = normalize_args(args)
    # Initialize archive
    print("Will attempt to clone archive.")
    print("Note that if it runs for more than an hour this process will time out and fail.")
    print("You can clone the repository manually if the timeout is a problem.")
    call(["git", "clone", args.git_init, os.path.basename(args.archive)], cwd=os.path.dirname(args.archive), timeout=3600)


def update(args):
    # Check for updates
    args = normalize_args(args)
    assert os.path.exists(args.archive), "Archive must exist: "+args.archive+" (use git-clone if you're trying to initialize an archive)"
    assert os.path.isdir(args.archive), "Archive must be a directory: "+args.archive
    
    db_dir = os.path.join(args.archive, ".db")
    
    if (not os.path.isdir(db_dir)):
        print ("Creating JSON database folder: "+db_dir)
        os.mkdir(db_dir, mode=0o755)
    
    for book_id in os.listdir(args.archive):
        book_dir = args.archive+"/"+book_id
        if (os.path.isdir(book_dir) and re.match("^\d+$", book_id)):
            print ("Processing book: "+book_id)
            db_filename = db_dir+"/"+book_id+".json"
            db = load_data(db_filename)
            
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
                assert 0 == call(["git", "reset"], cwd=args.archive, timeout=60)
                assert 0 == call(["git", "add", os.path.relpath(book_dir, args.archive)], cwd=args.archive, timeout=60)
                assert 0 == call(["git", "commit", "-m", "Updated book: "+book_id], cwd=args.archive, timeout=60)
                assert 0 == call(["git", "push"], cwd=args.archive, timeout=60)
                
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


def normalize_args(args):
    args.archive = os.path.normpath(args.archive)
    if args.git_init != None and urlparse(args.git_init).scheme == "":
        args.git_init = os.path.normpath(args.git_init)
    return args


def run_tests():
    args = init_test()
    if not os.path.exists(args.archive):
        git_init(args)
        
        print("Checking if repository is empty (will give 'fatal: ambigous argument' error if empty)...")
        empty_repo = call(["git", "rev-parse", "HEAD"], cwd=args.archive, timeout=5)
        if empty_repo:
            print("Repository is empty; initializing test repository...")
            
            os.makedirs(os.path.join(args.archive, "001", "subdir", "subsubdir"), mode=0o755)
            testfile = open(os.path.join(args.archive, "001", "subdir", "subsubdir", "file001.txt"), "a")
            testfile.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
            testfile.close()
            os.makedirs(os.path.join(args.archive, "002", "subdir"), mode=0o755)
            testfile = open(os.path.join(args.archive, "002", "subdir", "file002.txt"), "a")
            testfile.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
            testfile.close()
            
            assert 0 == call(["git", "add", "-A"], cwd=args.archive, timeout=5)
            assert 0 == call(["git", "commit", "-m", "initialized test repository"], cwd=args.archive, timeout=5)
            assert 0 == call(["git", "push"], cwd=args.archive, timeout=5)
        else:
            print("repository is not empty, will not initialize.")
    
    # make changes to files
    for book_id in os.listdir(args.archive):
        book_dir = args.archive+"/"+book_id
        if (os.path.isdir(book_dir) and re.match("^\d+$", book_id)):
            testfile = open(os.path.join(book_dir, "file.txt"), "a")
            testfile.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
            testfile.close()
    
    update(args)



def init_test():
    tmp_parent = tempfile.gettempdir()
    tmp_remote = os.path.join(tmp_parent, "archive-remote")
    tmp_local = os.path.join(tmp_parent, "archive-local")
    assert os.path.isdir(tmp_remote) or not os.path.exists(tmp_remote) and os.path.isdir(tmp_parent), "Unable to create temporary remote: " + tmp_remote
    assert os.path.isdir(tmp_local) or not os.path.exists(tmp_local) and os.path.isdir(tmp_parent), "Unable to create temporary local: " + tmp_local
    if not os.path.exists(tmp_remote):
        os.mkdir(tmp_remote, mode=0o755)
        assert 0 == call(["git", "init", "--bare"], cwd=tmp_remote, timeout=5)
    args = argparse.Namespace()
    args.archive = tmp_local
    args.git_init = tmp_remote
    return args


if __name__ == "__main__":
    main(sys.argv[1:])
