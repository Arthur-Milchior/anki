## Changing the delay

This configuration is slightly technical, you may probably ignore
it. 

In order to explain what it does, I need to explain some details about
anki's internal. I'll use an example.
#### Context 

Let's say you review a card the 31rst of December, and that this card
should be reviewd again 4 days later (i.e the 4th of January). We say
that the card's interval is 4 day. If you press «good» the 4th of
January, then the next interval will be 4*1.5=6 days, and you'll have
to see this card again the 10-th of january. (Here, 1.5 is an example,
the number may change).

Now, let's imagine that, instead of reviewing the card the 4th, you
review this card the 10th of january. This card is two day late. The
question we have to consider is: what is the new interval ? Is it
still 4*1.5=6 days ? That makes no sens, if you successfully recalled
the cards after 10 days, there is no reason to use a 6 days interval
next. After all the real interval (i.e. theoretical inverval +
lateness) was already 10 days.

Should the new interval be (4+6)*1.5 = 15 days ? Well, that may be an
overkill. If the card is really easy, ok. But if the card is "good",
15 days is still a big step for such a new card. So taking the whole
real interval into account is a bad idea.

Thus, what anki does, is that: instead of using the theoretical
interval or the real interval  it uses a ```planning interval``` whose
value is somewhere between the theoretical and the the real
interval. More precisely, this ```planning interval``` interval is the
sum of the theoretical interval and of the lateness, divided by 4 if
you pressed hard, by 2 if you pressed good, and by 1 if you pressed
easy. 

In our previous example, the new interval will be (4+6)*1.5 if you
press easy, (4+(6/2))*1.5=11 days if you press «good» and
(4+(6/4))*1.5=8 days if you press «hard». (Once again, its a
simplification. The value 1.5 is an example.)

#### With this add-on
Now, instead of just seeing this card late, you decide to use this
add-on to add 6 days to every card. Thus, this card is considered to
be due the 10th of january.

If you actually review it the 10-th of January, anki's will consider
that it's not late. I have no control over that. Because, you may see
this card on your phone, on ankiweb, on a computer where this add-on
is not installed... That's the second constraint mentionned above.

What I can control is the value of the theoretical interval. I can
decide to add 6 days to it. Or only 6/2=3 days. That is, in order to
simulate anki's normal behavior, I'll have to guess in advance whether
you'll press hard, good or easy, to simulate it.


#### The configuration
The configuration parameter "interval coefficient" should be a
number. When you use the add-on stating that you want to add n days to
every cards, the theoretical interval will be incremented of
n*"interval coefficient" days. If this configuration is set to 0, the
theoretical interval is not changed. If this configuration is set to
1, then every days of delay is added as interval.


## The case of negative days

There is a configuration "coefficient for negative". Its possible values
are:
* True: in which case the coefficient for positive number is also used
  for negative
* False: in which case when a negative number of day is added,
  intervals are note changed
* a number: in which case this number is added, as is in the positive
  case.

It is not clear whether changing the interval is a good idea in
general.

### Why you may want to change intervals for negative number of days.

If you added 10 days, and then remove 3 days, you probably want to
change the interval. So in the end, it will be like you directly added
7 days. (Note that because of rounding error, adding 10 and removing 3
days is not exactly the same as directly adding 7 days)

### Why you may want not to change intervals

Imagine that you have added 7 days to all cards.
Then you see a new card. Let's say it now has an interval of four
days.

If you decide to remove 7 days to every cards. This card will have its
interval decreased, and will have an interval of one. And there is
absolutly no reason to want it. The problem here is that this card was
new when you added days, and is not new anymore. Thus, only the second
action is applied to it.