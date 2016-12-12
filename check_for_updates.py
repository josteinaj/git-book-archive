#!/usr/bin/python3
# -*- coding: utf-8 -*-

# - Always ensure that the repository stays on the master branch; never change it
# - Don't push to the remote master branch; only this script should be allowed to do that
# - To edit files, either:
#     - Edit the files in-place and this script will automatically commit the changes
#     - Push branches to remote and include `[archive merge]` or `[merge archive]` in the comment to merge the branch (TODO: feature not needed?)

import sys
if sys.version_info[0] != 3:
    print("Python version 3.x required")
    sys.exit(1)

from urllib.parse import urlparse
import argparse
import os
import shutil
import re
import json
import tempfile
import time
import traceback
from dateutil import parser
from datetime import datetime, timedelta
from pprint import pprint
from subprocess import call, check_call, check_output
import socket


def main(argv):
    # get lock to avoid multiple simultaneous instances of this script
    get_lock(os.path.basename(__file__))
    
    if '--run-tests' in argv:
        run_tests("--forever" in argv)
    else:
        parser = argparse.ArgumentParser(description="Monitors a book archive and commits changes to git.")
        subparsers = parser.add_subparsers(title='subcommands', metavar="")
        
        parser_update = subparsers.add_parser("update", help="Check archive for changes.")
        parser_update.add_argument("archive", help="Path to the archive.", metavar="PATH")
        parser_update.add_argument("-f", "--forever", help="Loop script forever.", action='store_true')
        parser_update.set_defaults(func=update)
        
        parser_init = subparsers.add_parser("git-init", help="Initialize archive from remote git repository.")
        parser_init.add_argument("archive", help="Path to the archive.", metavar="PATH")
        parser_init.add_argument("git_url", help="Initialize the archive from this git repository.", metavar="URL")
        parser_init.set_defaults(func=git_init)
        
        args = parser.parse_args()
        if "func" in args:
            args.func(args)
        else:
            print(parser.format_help())


def git_init(args):
    args = normalize_args(args)
    print("---------------------------")
    print("  initialize archive       ")
    print("---------------------------")
    print("Will attempt to clone archive.")
    print("Note that if it runs for more than an hour this process will time out and fail.")
    print("You can clone the repository manually if the timeout is a problem.")
    check_call(["git", "clone", args.git_url, os.path.basename(args.archive)], cwd=os.path.dirname(args.archive), timeout=3600)
    gitignore_filepath = os.path.join(args.archive, ".gitignore")
    gitignore = []
    if os.path.exists(gitignore_filepath):
        with open(gitignore_filepath) as f:
            gitignore = f.readlines()
    if ".db/\n" not in gitignore:
        with open(gitignore_filepath, "a") as f:
            f.write("\n")
            f.write("# ignore database folder\n")
            f.write(".db/\n")
        check_call(["git", "reset"], cwd=args.archive, timeout=60)
        check_call(["git", "add", os.path.relpath(gitignore_filepath, args.archive)], cwd=args.archive, timeout=60)
        check_call(["git", "commit", "-m", "Added .db/ to .gitignore"], cwd=args.archive, timeout=60)
        check_call(["git", "push"], cwd=args.archive, timeout=60)


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
    assert os.path.exists(args.archive), "Archive must exist: "+args.archive+" (use git-init if you're trying to initialize an archive)"
    assert os.path.isdir(args.archive), "Archive must be a directory: "+args.archive
    try:
        checkout_master_output = check_output(["git", "checkout", "master"], cwd=args.archive, universal_newlines=True, timeout=60) # we must always be on the master branch!
    except CalledProcessError as e:
        checkout_master_output = e.output
    checkout_master_output = checkout_master_output.splitlines()
    needs_merge = False
    for line in checkout_master_output:
        if "needs merge" in line:
            needs_merge = True
            break
    if needs_merge:
        print("branch seems to require a merge, probably due to a previously failed merge; aborting merge")
        check_call(["git", "merge", "--abort"], cwd=args.archive, timeout=60)
        check_call(["git", "checkout", "master"], cwd=args.archive, timeout=60) # we must always be on the master branch!
    
    db_dir = os.path.join(args.archive, ".db")
    
    if (not os.path.isdir(db_dir)):
        print("Creating JSON database folder: "+db_dir)
        os.mkdir(db_dir, mode=0o755)
    
    main_db_filename = db_dir+"/_main.json" # assume no book will ever have the UID "_main"
    main_db = load_data(main_db_filename)
    
    # Determine if git fetch/pull should be performed
    last_git_fetch = None
    should_git_fetch = False
    if ("last_git_fetch" in main_db):
        last_git_fetch = parser.parse(main_db["last_git_fetch"])
    else:
        last_git_fetch = datetime.utcnow() - timedelta(days=1)
    if (last_git_fetch > datetime.utcnow() - timedelta(minutes=10)):
        # the previous git fetch for the book has changed
        main_db["last_git_fetch"] = str(datetime.utcnow())
        save_data(main_db_filename, main_db)
        should_git_fetch = True
    
    
    # Iterate books
    for format_id in os.listdir(args.archive):
        format_dir = os.path.join(args.archive, format_id)
        if format_id.startswith(".") or format_id.startswith("_") or not os.path.isdir(format_dir):
            continue
        print("format_dir: "+format_dir)
        for book_id in os.listdir(format_dir):
            book_dir = os.path.join(format_dir, book_id)
            print("book_dir: "+book_dir)
            if (os.path.isdir(book_dir) and not book_id.startswith(".") and not book_id.startswith("_")):
                print("Processing book: "+book_id)
                db_filename = os.path.join(db_dir, format_id+"_"+book_id+".json")
                db = load_data(db_filename)
                
                last_modified = None
                for root, dirs, files in os.walk(book_dir):
                    for name in files:
                        modified = modification_date(os.path.join(root, name))
                        if (last_modified == None or modified > last_modified):
                            last_modified = modified
                            print(book_id+": "+name+" is modified...")
                    for name in dirs:
                        modified = modification_date(os.path.join(root, name))
                        if (last_modified == None or modified > last_modified):
                            last_modified = modified
                
                previous_modified = None
                if ("last_modified" in db):
                    previous_modified = parser.parse(db["last_modified"])
                else:
                    previous_modified = datetime.utcnow() - timedelta(days=1)
                
                if (last_modified > previous_modified and last_modified > datetime.utcnow() - timedelta(seconds=60)):
                    # the last modified timestamp for the book has changed
                    print("Last modified timestamp indicates a change in "+book_id)
                    
                    db["last_modified"] = str(last_modified)
                    db["id"] = book_id
                    save_data(db_filename, db)
                    
                    check_call(["git", "reset"], cwd=args.archive, timeout=60)
                    check_call(["git", "add", os.path.relpath(book_dir, args.archive)], cwd=args.archive, timeout=60)
                    diff = check_output(["git", "--no-pager", "diff", "--staged"], cwd=args.archive, universal_newlines=True, timeout=60)
                    if diff:
                        check_call(["git", "commit", "-m", "Updated book: "+book_id], cwd=args.archive, timeout=60)
                        check_call(["git", "push"], cwd=args.archive, timeout=60)
                
    
    print("---------------------------")
    print("  check for pull requests  ")
    print("---------------------------")
    if should_git_fetch:
        check_call(["git", "fetch"], cwd=args.archive, timeout=3600)
    unmerged_branches = check_output(["git", "branch", "--no-merged=HEAD", "--remote", "--no-color"], cwd=args.archive, universal_newlines=True, timeout=60)
    unmerged_branches = unmerged_branches.splitlines()
    for branch in unmerged_branches:
        full_branch = re.sub(r"^.*?([^ ]+)$", r"\1", branch)
        short_branch = re.sub(r".*/", "", full_branch)
        print(branch)
        commit_message = check_output(["git", "--no-pager", "log", full_branch+"~1.."+full_branch, "--"], cwd=args.archive, universal_newlines=True, timeout=60)
        commit_message = commit_message.splitlines()
        tag = None
        for line in commit_message:
            if re.match(r".*\[archive [a-z]+\].*", line):
                tag = re.sub(r".*\[archive ([a-z]+)\].*", r"\1", line)
                break
            if re.match(r".*\[[a-z]+ archive\].*", line):
                tag = re.sub(r".*\[([a-z]+) archive\].*", r"\1", line)
                break
        if tag == "merge":
            print("Will attempt to merge "+full_branch)
            #call(["git", "branch", "-D", short_branch], cwd=args.archive, timeout=60) # in case remote branch has deviated from local branch with same name
            check_call(["git", "pull"], cwd=args.archive, timeout=60)
            return_code = call(["git", "merge", full_branch, "--no-ff", "-m", "Merged "+full_branch+" into master"], cwd=args.archive, timeout=60)
            if return_code:
                conflict_files = check_output(["git", "--no-pager", "diff", "--name-only", "--diff-filter=U"], cwd=args.archive, universal_newlines=True, timeout=60)
                conflict_files = conflict_files.splitlines()
                print("conflict files:")
                print(conflict_files)
                for conflict_file in conflict_files:
                    print("Merge conflict in "+conflict_file+"; using the one from "+full_branch)
                    call(["git", "checkout", "--theirs", conflict_file], cwd=args.archive, timeout=60)
                    call(["git", "add", conflict_file], cwd=args.archive, timeout=60)
                check_call(["git", "commit", "-m", "Merged "+full_branch+" into master"], cwd=args.archive, timeout=60)
            print("Merge complete")
            check_call(["git", "push"], cwd=args.archive, timeout=60)
            check_call(["git", "push", "origin", "--delete", short_branch], cwd=args.archive, timeout=60)
            call(["git", "branch", "-D", short_branch], cwd=args.archive, timeout=60) # clean up; no need to store other branches locally


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
    args.archive = os.path.normpath(args.archive)
    if "git-url" in args and urlparse(args.git_url).scheme == "":
        args.git_url = os.path.normpath(args.git_url)
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
    if not os.path.exists(args.archive):
        git_init(args)
    if not os.path.exists(os.path.join(args.archive, "daisy202", "TEST_BOOK_001")):
        print("copying test books to archive...")
        
        shutil.copytree(os.path.join(os.path.dirname(os.path.realpath(__file__)), "test", "daisy202"), os.path.join(args.archive, "daisy202"))
        shutil.copytree(os.path.join(os.path.dirname(os.path.realpath(__file__)), "test", "epub3"), os.path.join(args.archive, "epub3"))
        
        check_call(["git", "add", "-A"], cwd=args.archive, timeout=60)
        check_call(["git", "commit", "-m", "copied test books to archive"], cwd=args.archive, timeout=60)
        check_call(["git", "push"], cwd=args.archive, timeout=60)
    
    print("------------------------------")
    print("  make a branch with changes  ")
    print("------------------------------")
    all_branches = check_output(["git", "branch", "--all", "--no-color"], cwd=args.archive, universal_newlines=True, timeout=60)
    all_branches = all_branches.splitlines()
    new_branch_name = "test-branch-"+str(len(all_branches))
    check_call(["git", "checkout", "-b", new_branch_name], cwd=args.archive, timeout=60)
    run_tests_prepend_html(os.path.join(args.archive, "daisy202", "TEST_BOOK_001", "content.html"))
    check_call(["git", "add", "-A"], cwd=args.archive, timeout=60)
    check_call(["git", "commit", "-m", "[archive merge] change in branch #"+str(len(all_branches))], cwd=args.archive, timeout=60)
    check_call(["git", "push", "--set-upstream", "origin", new_branch_name], cwd=args.archive, timeout=60)
    check_call(["git", "checkout", "master"], cwd=args.archive, timeout=60)
    
    print("---------------------------")
    print("  make changes to files    ")
    print("---------------------------")
    run_tests_append_html(os.path.join(args.archive, "daisy202", "TEST_BOOK_001", "content.html"))
    run_tests_append_html(os.path.join(args.archive, "epub3", "TEST_BOOK_002", "EPUB", "TEST_BOOK_002-02-chapter.xhtml"))
    
    update(args)


def run_tests_prepend_html(filepath):
    with open(filepath) as f:
        content = f.readlines()
    with open(filepath, 'w') as f:
        found_first_p = False
        for line in content:
            if (not(found_first_p) and "<p" in line):
                f.write("        <p>%s</p>\n" % datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC"))
                found_first_p = True
            f.write("%s" % line)


def run_tests_append_html(filepath):
    with open(filepath) as f:
        content = f.readlines()
    with open(filepath, 'w') as f:
        for line in content:
            if ("</body" in line):
                f.write("        <p>%s</p>\n" % datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f UTC"))
            f.write("%s" % line)


def init_test():
    tmp_parent = tempfile.gettempdir()
    tmp_local = os.path.join(tmp_parent, "archive-local")
    tmp_remote = os.path.join(tmp_parent, "archive-remote")
    assert os.path.isdir(tmp_local) or not os.path.exists(tmp_local) and os.path.isdir(tmp_parent), "Unable to create temporary local: " + tmp_local
    assert os.path.isdir(tmp_remote) or not os.path.exists(tmp_remote) and os.path.isdir(tmp_parent), "Unable to create temporary remote: " + tmp_remote
    if not os.path.exists(tmp_remote) and not os.path.exists(os.path.join(tmp_local, ".git")):
        os.mkdir(tmp_remote, mode=0o755)
        check_call(["git", "init", "--bare"], cwd=tmp_remote, timeout=5)
    args = argparse.Namespace()
    args.archive = tmp_local
    args.git_url = tmp_remote
    args.forever = False
    return args


if __name__ == "__main__":
    main(sys.argv[1:])
