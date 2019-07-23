from .config import getUserOption
from anki.lang import _
import os

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))
js_file = os.path.join(__location__,"deckbrowser.js")
css_file = os.path.join(__location__,"defaultcss.css")

with open(js_file,"r") as f:
    js= f.read()
with open(css_file,"r") as f:
    css= f.read()


######################
#header related html #
######################
start_header = """
  <tr style = "vertical-align:text-top">"""

deck_header = f"""
    <th colspan = 5 align = left>
      {_("Deck")}
    </th>"""
def column_header(heading, colpos):
    return f"""
    <th class = "count ui-draggable ui-draggable-handle ui-droppable" colpos = "{colpos}">
      <a onclick = "return pycmd('optsColumn:{colpos}');">
        {_(heading)}
      </a>
    </th>"""

option_header = """
    <th></th>"""

option_name_header = """
    <td></td>"""

end_header = """
  </tr>"""



##############
#deck's html #
##############
def start_line(klass,did):
    return f"""
  <tr class = '{klass}' id = '{did}'>"""

def collapse_children_html(did,name,prefix):
    return f"""
      <a class = collapse onclick = 'return pycmd("collapse:{did}")' id = "{name}" href = "#{name}" >
         {prefix}
      </a>"""
collapse_no_child = """
      <span class = collapse></span>"""

def deck_name(depth,collapse,extraclass,did,cssStyle,name):
    return f"""
    <td class = decktd colspan = 5>
      {"&nbsp;"*6*depth}{collapse}
      <a class = "deck{extraclass}" onclick = "return pycmd('open:{did}')">
        <font style = '{cssStyle}'>
          {name}
        </font>
      </a>
    </td>
"""

def number_cell(colour, number, description):
    if description is None or description is False:
        description = ""
        t= f"""
    <td align = 'right'>"""
    else:
        description = f"""
      <span class = 'tooltiptext'>
        {description}
      </span>"""
        t= f"""
    <td align = 'right' class = 'tooltip'>"""
    # if number:
    t+=f"""
      <font color = '{colour}'>
        {number}
      </font>"""
    if description:
        t+=f"""
      {description}"""
    t+="""
    </td>"""
    return t


def gear(did):
    return f"""
    <td align = center class = opts>
      <a onclick = 'return pycmd(\"opts:{int(did)}\");'>
        <img src = '/_anki/imgs/gears.svg' class = gears>
      </a>
    </td>"""

def deck_option_name(option):
    return f"""
    <td>
      {option}
    </td>"""

end_line = """
  </tr>"""

def bar(name, width, left, color, overlay):
    return f"""
          <div class="tooltip bar" style="position:absolute; height:100%; width:{width}%; background-color:{color}; left :{left}% ;">
            <!-- {name}-->
            <span class="tooltiptext">
              {overlay}
            </span>
          </div>"""

def progress(content):
    return f"""
      <div class="progress" style="position:relative;	height:1em;	display:inline-block;	width:100px;		">{content}
      </div>"""
