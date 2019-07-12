# Forked Anki, Alpha version
-------------------------------------

This is the development branch of a forked version of Anki. For the official, please see [https://apps.ankiweb.net](https://apps.ankiweb.net).

## Description
This is a version of anki in which multiple add-ons are already incorporated. I only incorporated non-disruptive add-ons with respect to the way Anki works fundamentally. Examples of feature added include Copy notes, Batch edit, Exporting from browser, Postponing cards, Increasing speed of some operations, Keeping some long term back-up, Giving the name of cards which will be deleted instead of their index... For a complete list of change in Forked, please see  [https://github.com/Arthur-Milchior/anki/blob/fork/difference.md](difference.md).

I believe this fork is a crucial addition to Anki, because it allows you to have plenty of new and convinient features without having to wade through the list of all add-ons. Furthermore, it deals with the issue of incompatibility between add-ons, which can be difficult to manage. Finally, it also allows for graphical configuration instead of a json-edit based one.

### Add-on compatibility
This fork is theoritically equivalent to anki and should therefore be fully compatible with any add-ons. Any already installed add-ons that is being installed again will simply be ignored

### Alpha specificity
This fork is still in alpha and in a very early stage. This mean it is not as ready-to-use as I would like - you need to download the github code and execute runanki on it instead of having an archive ready, as of now.
If you want to be an alpha-tester, please do notify me, I am still in need for some.

## Notes for devs:
### Why fork is easier than add-on
Honestly, I find that incorporating code in Anki is far easier than add-ons. Because:
* I often need to monkey patch a method by copying anki's method, adding it in an add-on, and changing a single line. This is a problem because it means  I have copied the method from Anki and am detached from its code - if Anki does change the method the changes are not pushed through. This leads to unexpected bugs that are hard to track down, and that only appears when Anki is updated to a newer version. By using a fork, and merging regularly Anki with the forked version, this is no longer an issue.
* There is no problem of add-on compatibility. Indeed, if many add-ons change the same method, I can just do all the change in one file, instead of having to find an arcane way to merge them. Currently with add-ons, I have to create yet another add-on, merging the many incompatible add-ons in a new one. This is what I did, for example, when I created an add-on merging «multiple column editor» and «frozen fields», which is not an elegant solution.
* Some methods are extremely lengthy, such as ``fixintegrity`` (i.e. "Check database"). With a fork, I can now split this method in many smaller ones.
* I can use anki's preference window to configure everything, instead of having to relies on json files or in specialized configuration windows.

### How to add features
For a detailled explanation, see [How to add an add-on in the code.md](How to add an add-on in the code)

### Branches

To run from source, please see README.development.

If you are interested in contributing changes to this Fork, just contact arthur@milchior.fr
