# Git Book Archive
by Jostein Austvik Jacobsen

*NOTE*: This is currently just an experiment.

Intended for use in an organization to track and handle changes in their "master archive".

Requirements:
- Python 3
- Docker

## check_for_updates.py

This python script should be set up to run in a loop. The script must have complete control
over the master branch of the git remote, no-one else should commit to the master branch.
Branches where the commit message for the branch tip contains either `[archive merge]`
or `[merge archive]` will be merged into master if possible (essentially a pull request).

Each commit will only contain changes for a single book. This can be useful for
continous integration tools that trigger whenever there's a new git commit.


## handle_updates.py

This python script should be set up to run in a loop as well. It will handle all new
commits in the remote master branch according to the rules defined in a config file.
The file handle_updates.json will be used if a custom config file is not defined.
