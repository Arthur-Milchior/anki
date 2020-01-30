# How to decide whether a card should be generated/deleted

The algorithm change in 2.1.20. I'll update this document when 2.1.20
won't be in beta anymore.

## Context

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
mandatory fields.

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

# Examples

Let's now consider some examples which were counter-intuitive for me.

Anki is changing the way it decides which card are generated. Which makes me look at the generating algorithm to find examples where there actually are differences. I'm realizing fun things with the old algorithm.

Take
```
{{#Conditional}}{{Field1}} {{Field 2}}  {{/Conditional}}
```
This card is generated as soon as "Conditional" is filled. Because Anki computed that Field1 is not mandatory. Field2 is not mandatory. So the only mandatory field is "Conditional".

Take
```
{{#Conditional}}
{{Field1}}
{{/Conditional}}{{Field2}}
```
If only "Field2" is filled, the card is generated. This is to be expcted. What's more surprising is that if "Conditional" is filled, then the card is generated. This is because the card is different when "Conditional" is filled or not. Indeed, there are two more space returns when the field id filled.

If you remove the line breaks, e.g. ```
{{#Conditional}}{{Field1}}{{/Conditional}}{{Field2}}
```
then the card is generated only when Field2 is filled. Field1 and Conditional are not considered anymore for generation. Which becomes even funnier when you realize that if you remove the "field2", ```
{{#Conditional}}{{Field1}}{{/Conditional}}
```
generates a card as soon as both field1 and conditional are filled. The reason for this difference is that now, some fields are mandatory; while in the previous case no fields were mandatory and so anki applied a different rule to check for card generation.

Now take ```
{{^Conditional}}{{Field1}}{{/Conditional}}
```
Power user of Anki knows that this card will never be generated. That's even what I wrote above.

But have you considered:
```
{{^Conditional}}{{Field1}} {{/Conditional}}
```
or
```
{{^Conditional}}{{Field1}}{{/Conditional}}{{#Conditional}} {{/Conditional}}
```
? Those cards are generated if and only if all fields are filled, except for conditional. And I really mean, "all fields". Even the fields which are not in this template. If the note type has a field "Field2", it should be filled, othewise the card won't be generated. The reason behind this is quite silly. Anki realize that when all fields are filled, the result is different than when all fields are empty (there is a space, after all !). Anki then checks whether any field is mandatory by filling all fields and then checking if it sees a field's value in the result. And actually, when it does not fill "Conditional", it sees some value, which means that "Conditional" is "not mandatory" (indeed, it's actually forbidden). Furthermore, when "Field1" or "Field2" is not filled but "Conditional" is filled, it sees no value in the card's question. So it believes that "Field1" is mandatory and that "Field2" is mandatory.

Let's make another small twist. Take
```
{{^Conditional2}}{{^Conditional}}{{Field1}}{{/Conditional}}{{/Conditional2}}
```
This card can't be generated (this kind of makes sens)
But if you add a space
```
{{^Conditional2}}{{^Conditional}}{{Field1}} {{/Conditional}}{{/Conditional2}}
```
then this card is generated if and only if all fields are filled (in which case, card is empty, but we don't care). Because, following the explanation above, anki incorectly believes that all fields are mandatory !

