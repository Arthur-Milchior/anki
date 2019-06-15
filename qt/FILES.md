As the file with [same name in parent directory](../FILES.md), this
document contains a succint description of the content of each file
from this folder.

This folder deal with all of the front end of anki. Contrary to what
its name suggest, it does not contains only code which deal with qt.

# designer
This subfolder contains Qt Creator files, used to generate the
front-end windows.

# aqt
This file contains all front-end code dealing with the windows created
in designer. It also contains code to direcetly generate a few form windows.

# ts
Contains all of the files related to the "web" part of the
back-end. Contrary to its name, it does not only contains typescript,
but also html, css.

# aqt_data
Contains some web related library (mathjax, jquery, jquery-ui... )

# ftl
Contains English version of String displayed to users. It currently
only contains most recent strings, as most string as directly in the
code.

# polib
Files related to the [polib library](https://pypi.org/project/polib/),
related to translation.

# tests
Contains tests related to the back-end. Currently related to add-ons
and translations

# tools
Contains tools used to compile back-end code into something that can
be executed in anki.
