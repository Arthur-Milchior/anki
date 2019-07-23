/* Copyright: Ankitects Pty Ltd and contributors
 * License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html */


function init() {


    $("tr.deck").draggable({
        scroll: false,

        // can't use "helper: 'clone'" because of a bug in jQuery 1.5
        helper: function (event) {
            return $(this).clone(false);
        },
        delay: 200,
        opacity: 0.7
    });
    $("th.count").draggable({
        scroll: false,

        // can't use "helper: 'clone'" because of a bug in jQuery 1.5
        helper: function (event) {
            return $(this).clone(false);
        },
        delay: 200,
        opacity: 0.7
    });
    $("tr.deck").droppable({
        drop: handleDropEvent,
        hoverClass: 'drag-hover'
    });
    $("th.count").droppable({
        drop: columnDropEvent,
        hoverClass: 'drag-hover'
    });
    $("tr.top-level-drag-row").droppable({
        drop: handleDropEvent,
        hoverClass: 'drag-hover'
    });
}
$(init);

function handleDropEvent(event, ui) {
    var draggedDeckId = ui.draggable.attr('id');
    var ontoDeckId = $(this).attr('id') || '';

    pycmd("drag:" + draggedDeckId + "," + ontoDeckId);
}

function columnDropEvent(event, ui) {
    var draggedDeckId = ui.draggable.attr('colpos');
    var ontoDeckId = $(this).attr('colpos') || '';
    pycmd("dragColumn:" + draggedDeckId + "," + ontoDeckId);
}
