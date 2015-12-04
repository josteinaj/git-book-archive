#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
if sys.version_info[0] != 3:
    print("Python version 3.x required")
    sys.exit(1)

#from urllib.parse import urlparse
#import argparse
#import os
#import shutil
#import re
#import json
#import tempfile
#import time
#import traceback
#from dateutil import parser
#from datetime import datetime, timedelta
from pprint import pprint
#from subprocess import call, check_call, check_output
#import socket


def main(argv):
    # get lock to avoid multiple simultaneous instances of this script
    get_lock(os.path.basename(__file__))
    
    if '--run-tests' in argv:
        run_tests("--forever" in argv)
    else:
        # TODO
#        parser = argparse.ArgumentParser(description="Monitors a book archive and commits changes to git.")
#        subparsers = parser.add_subparsers(title='subcommands', metavar="")
#        
#        parser_update = subparsers.add_parser("update", help="Check archive for changes.")
#        parser_update.add_argument("archive", help="Path to the archive.", metavar="PATH")
#        parser_update.add_argument("-f", "--forever", help="Loop script forever.", action='store_true')
#        parser_update.set_defaults(func=update)
#        
#        parser_init = subparsers.add_parser("git-init", help="Initialize archive from remote git repository.")
#        parser_init.add_argument("archive", help="Path to the archive.", metavar="PATH")
#        parser_init.add_argument("git_url", help="Initialize the archive from this git repository.", metavar="URL")
#        parser_init.set_defaults(func=git_init)
        
        args = parser.parse_args()
        if "func" in args:
            args.func(args)
        else:
            print(parser.format_help())


def update(args):
    if args.forever:
        while True:
            print()
            print("============================================================")
            print("Iteration start time: "+datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC")+"\n")
            print()
            
            try:
                update_iteration(args)
            except Exception as e:
                print("An exception occured while updating!")
                print()
                traceback.print_exc(file=sys.stdout)
            time.sleep(5)
            
            print("============================================================")
            print()
    else:
        update_iteration(args)
    

def update_iteration(args):
    print("---------------------------")
    print("  check for updates        ")
    print("---------------------------")
    args = normalize_args(args)
    
    # TODO


def load_data(db_filename):
    if (not os.path.isfile(db_filename)):
        print("Creating "+db_filename)
        with open(db_filename, 'w') as json_file:
            json.dump({}, json_file)
    
    try:
        with open(db_filename) as json_file:
            data = json.load(json_file)
    except Exception as e:
        print("Warning: Could not read JSON: "+db_filename)
        data = {}
    
    return data


def save_data(db_filename, data):
    with open(db_filename, 'w') as json_file:
        json.dump(data, json_file)


def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.utcfromtimestamp(t)


def normalize_args(args):
    #args.archive = os.path.normpath(args.archive)
    return args


def get_lock(process_name):
    # http://stackoverflow.com/a/7758075/281065
    if not(sys.platform == "linux" or sys.platform == "linux2"):
        print("WARNING: trying to aquire lock on non-Linux system")
    global lock_socket # Without this our lock gets garbage collected
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind('\0' + process_name)
        print('I got the lock')
    except socket.error:
        print('lock exists')
        sys.exit()


def run_tests(forever):
    if forever:
        while True:
            run_tests_iteration()
            time.sleep(60)
    else:
        run_tests_iteration()
    
    
def run_tests_iteration():
    args = init_test()
    # TODO
    update(args)


def init_test():
    # TODO
    return args


if __name__ == "__main__":
    main(sys.argv[1:])
