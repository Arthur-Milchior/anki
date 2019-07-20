# Configuration of anki's addon Enhanced Main

1. We first discuss the various small configurations related to the whole add-on.
1. We then explain how to configure each column.
1. We then explain how to configure coloring related to empty deck.
1. We finally explain how to configure coloring related to marked cards.

## Miscelaneous
In this section, we describe various small configurations related to the whole add-on.

### Option
Whether you want to display the deck's option's name, at the end of its line.


### cap value
By default, without add-on, anki never show number greater than a thousand. Instead, it shows 1000+. You can decide to change a thousand by an arbitrary number. Or leave this value to null, and always show the real value.

Note that capping to a thousand does not usually make the rendering quicker.

### Dot in number
Whether you want a big number such as 34968 to be shown as "34.968" or as "34968".

### color zero
The color to use for the zero. If it's a string, use always this color. By default in anki, it's a kind of grey. If you set it to false (default in this add-on), then the zero is not shown at all. You car remove this line or set it to  null to ensure that the default column is used. To obtain the grey which is the default value in anki, you can set the color to "#e0e0e0".

## Columns

Each column should occur after the line "columns" :[, and before the line with a closing bracket ]. The order of the lines is important, since it's the order in which columns will be displayed by anki. This means that you can reorder columns in anki by reordering the lines in the configuration. You can copy a line to display a column multiple time (for example, once using percent, and another time using absolute number).

Each column is represented between an opening curly bracket {, and a closing curly bracket }. Each column uses 8 parameters, each represented as a pair
>>key:value
We'll tell you the meaning of each key, whether you can change its value, and what will this change do.

### Name
The first value is a description, which will tell you what the column represent. Do NOT alter this value, or the add-on will raise an error.

### Description
A description of the content of the column. This is not used by anki, it allows you to decide whether you want the column or not while you edit the configuration.


### Present
The value for the key "present" is either true or false. If the value is true, the column will be displayed. Otherwise, it will not. Note that you can also delete the entire column from the configuration, instead of changing the value to false.

If this value is absent, by default, it is assumed that it should be true.

### Header
The header of the column. If you leave «null» then the default header will be used. This description will be translated as much as it is possible to do it automatically. However, you can also choose to write your own description. You can use html in this description. I.e. you should use "<br/>" when you want a newline.

### Overlay
The text shown when your mouse is over a number. It will describe what this number represent. You can remove this key or set it to false if you want no description to be present. And leave this value to null if you want to use the default value.

### Color
The color in which the number is written in this column. You can use any color acceptable in an HTML document. The most standard color's name should work. None means that it should use the same color than in the statistic window, if this color exists, or the default color otherwise.

###  Percent
true or false whether you want to show the percent of cards satisfying this colun condition. For example, 23% of cards are new. Note that sometime, this would not make sens. For example, for the column «cards», the value will always be 100% (unless the deck is empty). For the column notes, the number would not really make any sens (formally, you'd get the percent of cards which is the first of its sibling in this deck).

By default, if percent is absent, it is assumed to be false.

### Absolute
Whether you want an absolute number in your column. That is, a number which is not a percent, but an exact number.

By default, this value is false if Percent is set to true, otherwise its default value is true.

### Subdecks
When you consider a deck which has subdecks, you may want to consider cards in subdecks (it is done when the value is true), or you may want to ignore them (it is done when the value is false).

### Short name
Please do not touch this value. It is used internally by the add-on. If you edit this value, the add-on will throw an error message and anki won't be able to display the main window.

## Coloring decks
The author of this add-on want to know when a deck is empty. This is very important to him, because he want to add new cards in them as soon as possible. Thus, this add-on change the color of the name of empty decks, and of name of decks with an empty descendant.

The author also want to know which deck has marked card. Thus, the background of the deck's name with marked card change color.

Both of those configuration can be changed as explained in this section. In particular, you can turn one or both of those options off by setting "color empty" and "color marked" to false.
### Choice of color

#### Color empty
The color of the name of decks without new cards
#### Color empty descendant
The color of the name of decks with a descendant without new cards
#### Default color
The color of a deck whose every descendant has new cards.

#### Default column color
The color of the content of a deck, if no other color is specified.
#### ended marked background color
The color of the decks which has an ended deck with marked cards. The  notion of ended deck will be explained in the next section of this documentation.

#### marked background color
The color of deck who have marked cards but none of its descendant are both ended and has marked card.



### Deck modifier
A deck modifier is a symbol (or a word, etc..) whose presence in a deck name change the meaning of the deck. When the meaning is changed, the coloration is also change. It's not clear to the author of this add-on whether anyone appart from himself will need those, but if you want to use them, here is the explanation.

The first  three symbols currently has the same effect, but it may occur that one day this effect may change, according of what the author want to do.
#### End symbol
By default, this symbol is ";". It means that the deck is definitively done, and no new card may ever be added to it. When a deck has this symbol, neither itself nor its descendant will ever be colored.

#### Given up symbol
By default, this symbol is "/".To the author, it means that no new card will be added because this deck is either too hard, or not interesting enough.

#### Pause symbol"
By default, this symbol is "=". To the author, it means that more new card will be added latter, but right now it does not want anki to change the color of the deck's name. In a future version, there may be an option to change the color of those decks.
