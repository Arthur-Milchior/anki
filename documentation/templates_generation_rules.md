# How to decide whether a card should be generated/deleted

Anki's official
[documentation](https://apps.ankiweb.net/docs/manual.html#conditional-replacement)
is not really clear about the rules governing the generation of
cards. It states
> wrapping a template in `{{^Field}}` will not do what you expect.

But it let us guessing which are the cases creating trouble and which
cases are ok.

This document explains which are the rules which decides when a card
is generated or not. Those rules are implemented in
[models.py](../anki/models.py), in the method `_reqForTemplate`.

I assume that those rules are created in order to make anki quicker,
and less expensive in computation time. Alas, it makes anki more
complicated for power user.

## The rules

### Non cloze models

Anki generate the html content of some cards in some cases. It checks
this content to choose what kind of rules should be applied

First, anki generates the html of card where all fields are
empty. We'll call this content `empty content`. We'll use this
twice below.


#### Everything and Nothing
Anki generates the content where every fields contains "ankiflag". It
then checks whether the result is equal to `empty content`.
Intuitively, if you have the same result when everything is filled and
when everything is empty, it probably means that the template does not
consider its input. Anki then consider that this template can be
discarded.

In this case, the method `_reqForTemplate` returns `("none",[],[])`.

This is why the documentation state that you should not put everything
inside `{{^Field}}...{{/Field}}`. If you do that, then each time
the field `Field` is filled, the html content of this card is
empty. And thus anki believes that the note never generate any
content.

In particular it means that no card with this note type will ever be
generated.

### Removing one field
Now we know that some fields are actually used in the template,
and that, if every fields are filled, we have some content. Now, we
consider what happens if a single field is missing.

Thus, we generate the html content, when a field `Field` is empty,
and every other field contains the text "ankiflag". If we also find
"ankiflag" in the result, it means a field was shown, thus `Field`
is not mandatory.

If we don't find "ankiflag" in the result, we consider `Field` to
be mandatory.

If there is at least one mandatory field, `_reqForTemplate`
returns the pair `("all",l)` where `l` is the list of
mandatory flags.

In this case, cards are generated for this template if and only if all
of those "mandatory" fields are filled.

### Using a single field
We now assume that no fields are mandatory. In this case we check for
fields which are sufficient by themselves to generate a card with some
content.


Thus, we generate the content, when a field `Field` contains "1",
and every other fields is empty. If the result is not the same as the
html `empty content` computed above, then we consider that the
field `Field` is sufficient to generate the card.

Then `_reqForTemplate` returns `("any",l)` where `l` is
the list of sufficient field. Note that the list may be empty.

In this case, cards are generated for this template if and only if all
of those "mandatory" fields are filled.
