# git-book-archive
by Jostein Austvik Jacobsen

*NOTE*: This is currently just an experiment.

Intended for use in an organization to track changes in their "master archive".

The python script should be set up to run in a loop. This script must have complete control
over the master branch of the git remote, no-one else should commit to the master branch.
Branches where the commit message for the branch tip contains either `[archive merge]`
or `[merge archive]` will be merged into master if possible (essentially a pull request).

Each commit will only contain changes for a single book. This can be useful for
continous integration tools that trigger whenever there's a new git commit.
