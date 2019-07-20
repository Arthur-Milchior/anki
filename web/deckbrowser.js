/* Copyright: Ankitects Pty Ltd and contributors
 * License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html */

$(init);
var lastDragged = null;
function init() {
	$("th").draggable({
        helper: function (event) {
			lastDragged = "th";
            return $(this).clone(false);
        },
        delay: 200,
        opacity: 0.7
	});
    $("tr.deck").draggable({
        scroll: false,

        // can't use "helper: 'clone'" because of a bug in jQuery 1.5
        helper: function (event) {
			lastDragged = "tr";
            return $(this).clone(false);
        },
        delay: 200,
        opacity: 0.7
    });
    $("tr.deck").droppable({
        drop: handleDropEvent,
        hoverClass: 'drag-hover'
    });
    $("th").droppable({
        drop: handleColDropEvent,
        hoverClass: 'drag-hover'
    });
    $("tr.top-level-drag-row").droppable({
        drop: handleDropEvent,
        hoverClass: 'drag-hover'
    });
}

function handleDropEvent(event, ui) {
	if (lastDragged != "tr"){
		return
	}
    var draggedDeckId = ui.draggable.attr('id');
    var ontoDeckId = $(this).attr('id') || '';

    pycmd("drag:" + draggedDeckId + "," + ontoDeckId);
}
function handleColDropEvent(event, ui) {
	if (lastDragged != "th"){
		return
	}
    var draggedDeckId = ui.draggable.attr('colid');
    var ontoDeckId = $(this).attr('colid') || '';

    pycmd("dragColumn:" + draggedDeckId + "," + ontoDeckId);
}
