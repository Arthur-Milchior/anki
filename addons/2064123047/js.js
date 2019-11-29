function changeSize(fieldNumber){
	saveNow(true);
	pycmd("toggleLineAlone:"+fieldNumber);
}

function toggleFroze(fieldNumber){
	saveNow(true);
	pycmd("toggleFroze:"+fieldNumber);
}

function createDiv(ord,  fieldContent, nbCol){
	return "<td colspan={2}><div id='f{0}' onkeydown='onKey();' oninput='onInput();' onmouseup='onKey();'  onfocus='onFocus(this);' onblur='onBlur();' class='field clearfix' ondragover='onDragOver(this);' onpaste='onPaste(this);' oncopy='onCutOrCopy(this);' oncut='onCutOrCopy(this);' contentEditable=true class=field>{1}</div></td>".format(ord, fieldContent, nbCol);
}

function createNameTd(ord, fieldName, nbColThisField, nbColTotal, sticky, imgFrozen, imgUnfrozen){
	img = sticky?imgFrozen:imgUnfrozen;
	title =(sticky?"Unf":"F")+"reeze field "+fieldName;
	txt = "<td class='fname' colspan={0}><span>{1}</span>".format(nbColThisField, fieldName);
	if (nbColTotal>1){
		txt+= "<input type='button' value='Change size' tabIndex='-1' onClick='changeSize({0})'/>".format(ord);
	}
	txt+="<img width='15px' height='15px' title='{0}' src='{1}' onClick='toggleFroze({2})'/></td>".format(title, img, ord);
	//console.log("img is "+img);
	return txt;
}

function setFieldsMC(fields, nbCol, imgFrozen, imgUnfrozen) {
	//console.log("Set fields with "+nbCol+" columns")
	/*Replace #fields by the HTML to show the list of fields to edit.
	  Potentially change buttons

	  fields -- a list of fields, as (name of the field, current value, whether it has its own line)
	  nbCol -- number of colum*/
    var txt = "";
	var width = 100/nbCol;
	var partialNames = "";
	var partialFields = "";
	var lengthLine = 0;
    for (var i = 0; i < fields.length; i++) {
        var fieldName = fields[i][0];
        var fieldContent = fields[i][1];
		var alone = fields[i][2];
		var sticky = fields[i][3];
        if (!fieldContent) {
            fieldContent = "<br>";
        }
		//console.log("fieldName: "+fieldName+", fieldContent: "+fieldContent+", alone: "+alone);
		nbColThisField = (alone)?nbCol:1;
		fieldContentHtml = createDiv(i, fieldContent, nbColThisField);
		fieldNameHtml = createNameTd(i, fieldName, nbColThisField, nbCol, sticky, imgFrozen, imgUnfrozen)
		if (alone){
			nameTd = fieldNameHtml
			txt += "<tr>"+fieldNameHtml+"</tr><tr>"+fieldContentHtml+"</tr>";
		}else{
			lengthLine++;
			partialNames += fieldNameHtml
			partialFields += fieldContentHtml
		}
		//When a line is full, or last field, append it to txt.
		if (lengthLine == nbCol || ( i == fields.length -1 && lengthLine>0)){
			txt+= "<tr>"+partialNames+"</tr>";
			partialNames = "";
			txt+= "<tr>"+partialFields+"</tr>";
			partialFields = "";
			lengthLine = 0;
		}
    }
    $("#fields").html("<table cellpadding=0 width=100% style='table-layout: fixed;'>" + txt + "</table>");
    maybeDisableButtons();
}
