As the file with [same name in parent directory](../FILES.md), this
document contains a succint description of the content of each file
from this folder.

This folder contains all codes used for the python part of anki. It
contains both the source code, and a `build` directory containing the
result of the compilation.

# anki
This subfolder used to be named `/anki` and be at top level. It
contains all of the back-end code run by anki.

# .isort.cfg
Configuration for the program isort. Stating how to sort imports in
the code.

# Makefile 
This makefile is called by top level makefile to deal with the back
end specifically.

# requirements.dev

Requirements that should be found by make/(virtual env?) to be able to
execute the back-end code.

# tests
Tests for the backend specifically

# tools
Tools used to compile this code into the actual code used in the
background.

