# How to add a feature to this fork.

Create a branch, with parent baseFork. The name of this branch should
describe the feature you add. You then must modifies the code as
follow. See [branchs.md](branchs.md) to see what each branches are.

## Addon folder

In this folder, put a copy of the add-on, as it is in ankiweb when it
was added to this folder.

This ensure that, if an add-on is updated, you can check easily what
was updated. What's new today, and thus not what is not yet
incorporated in the fork code.

## differences.md

List your add-on in the list of change between this fork and regular
anki. Add the add-on number after the title.

Differences are listed in alphabetical order.

## Change to code.
In order to be as compatible as possible with Anki, I respected the
following rules. And I'll ensure that any pull request (if by luck,
anyone is interested in contributing), satisfies the same rules:

### Database
The database is not changed at all.  Otherwise, it creates risk of
incompatibility with ankidroid, ios and ankiweb. However, I allow to
add element in json's dictionaries.


### Method return
All methods returns the same kind of values in the forked version and
in Anki. So that any add-on calling those methods will have the
expected result.

As an example, imagine that anki's method `foo` returns an
int. Imagine that you want to return a pair, with the same int, and
also a Boolean.

Then, you can rename this method as `fooAndBool`, return the
pair. Then you can defined `foo` as `fooAndBool()[0]`.

### Method arguments.
All methods takes the same arguments. Any other arguments are keyword
argument. Most of the time, the default value could either ensure that
Anki is imitated, unless there is a good reason not to do it.

### aqt/addons.py

Add your add-on to the set of add-ons.

## Configuration options

If there are options to configure, add the buttons to
designer/preferences.ui

A checkbox is done as follow:
```xml
       <item>
        <widget class="QCheckBox" name="NAME">
         <property name="text">
          <string>TEXT</string>
         </property>
        </widget>
       </item>
```

A text as follows:
```xml
        <item>
         <widget class="QLabel" name="label_12">
          <property name="text">
           <string>TEXT</string>
          </property>
          <property name="wordWrap">
           <bool>true</bool>
          </property>
         </widget>
        </item>
```

They should be added between
```xml
           <string>&lt;html&gt;&lt;head/&gt;&lt;body&gt;&lt;p&gt;&lt;span style=&quot; font-weight:600;&quot;&gt;Extra&lt;/span&gt;&lt;br/&gt;Those options are not documented in anki's manual. They allow to configure the different add-ons incorporated in this special version of anki.&lt;/p&gt;&lt;/body&gt;&lt;/html&gt;</string>
          </property>
          <property name="wordWrap">
           <bool>true</bool>
          </property>
         </widget>
        </item>
```
and
```xml
        <item>
         <spacer name="verticalSpacer">
          <property name="orientation">
           <enum>Qt::Vertical</enum>
```

#### Editing configuration
In `aqt.preferences` you should edit `extraOptions`, adding a tuple
(even if it contains a single value, it should be a tuple !), with the
following element:
* name of the widget in the profile manager,
* default value (False or 0 by default)
* whether it's a check box (True by default)
* whether this value should be synchronidez (True by default)

Default values works as in any method call.

You can access this value from anywhere in the code in two distinct
ways. If the value is not synchronized, it is in the profile manager,
and thus by:
```Python
    from aqt import mw
    mw.pm.profile.get("xMLName", DefaultValue) if mw else DefaultValue
```
Note that, during test, `mw` is `None`. Otherwise, if the value is
synchronized, it is in the collection's configuration, and thus it is
accessed by
```Python
	col.conf.get("xMLName", DefaultValue)
```
