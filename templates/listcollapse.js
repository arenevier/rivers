(function($) {

    var close = function(img, elem) {
        img.attr("src", "arrow-left-mini.png");
        elem.attr("closed", "true")
        elem.children("ol, ul").hide();
    }
    var open = function(img, elem) {
        img.attr("src", "arrow-down-mini.png");
        elem.removeAttr("closed");
        elem.children("ol, ul").show();
    }

$.fn.listcollapse = function(initialclosed) {

    this.each(function() {
        var elem = $(this);
        if (elem.find("li").length) {
            var img = $('<img tabindex="0">');
            img.css({"margin-right": "4px", "vertical-align": "middle"});

            img.bind('click keypress', function(evt) {
                if (evt.type === 'keypress' && evt.keyCode !== 13) {
                    return;
                }
                if (elem.attr("closed")) {
                    open($(this), elem);
                } else {
                    close($(this), elem);
                }
            });

            if (initialclosed) {
                close(img, elem);
            } else {
                open(img, elem);
            }
            elem.children(":first-child").prepend(img)
        }
    });
    return this;
};
})(jQuery);
