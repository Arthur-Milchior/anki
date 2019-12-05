# List of branchs, and their meaning

Here is what my different git branches are, and the way I intend to develop more features:

intToConstant: same as Anki, but some integers are replaced by constant (i.e. variable). This make the code easier to read without changing it. I would love this to be incorporated into anki's main code, but Damien was note interested (and anyway, it's not ready yet, because I use f-string, and he can't use f-string)

Commented: Same code as Anki, containing all changes from intToConstant, and containing a lot of comments. Some of you may already know this branch, since many people liked or forked my repo. This should help add-on developpers to understand Anki. It also contains documentation of many feature of Anki, which I shared with you on reddit in the past.

baseFork: this branch contains everything done in Commented, plus everything needed by the fork. I.e. an Add-on class, documentation about how to add feature to Forked, etc...However, it contains no add-ons, thus it should behave as Anki.

nameOfAnAddOn: there are plenty of branches of this kind. Each branch add a single feature to baseFork. This allow to test this feature alone. It also means that each time me (or another dev) want to add a feature, he can directly does it in a code looking like anki's code.

fork: this branch merges all branches of the previous kind. I.e. it
contains all features. Most merge are easy to do, except when two
merges change the same method. However, merges are never totally
trivial, because each feature adds elements to some list, and git
needs help in order to know in which order to keep each element in the
list. For the sake of simplicity, I keep them in alphabetical order as
much as I can.
