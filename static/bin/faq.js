var faq_init = function() {
    $('faq').getElements('li').each(function(e) {
        var answer = e.getElement('.answer');

        // clone the element off-screen to get its height
        klone = answer.clone();
        klone.removeClass('hidden')
            .setStyles({
                left: '-999px',
                position: 'absolute',
                width: '670px'
        }).inject( $('faq'), 'bottom' );
        var height = klone.getHeight();
        klone.destroy();


        answer.setStyle('height', '0px')
            .set('tween', {duration: 'normal', fps: 100, link: 'ignore', property: 'height', unit: 'px'});
        e.getElement('.question').addEvent('click', toggle_answer.pass([e, answer, height]));
    });
};

var toggle_answer = function(q, a, max_height) {
    if (a.hasClass('hidden')) {
        a.removeClass('hidden');
        a.get('tween').start(max_height).chain(a.setStyle.pass(['height','auto'], a));
    } else {
        a.get('tween').start(a.getHeight(), 0).chain(a.addClass.pass('hidden', a));
        /*a.addClass('hidden');*/
    }
}

window.addEvent('domready', faq_init);
