odoo.define('rating_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var registry = require('web.field_registry')

    var FieldRating = AbstractField.extend({
        template: 'FieldRating',

        init: function() {
            this._super.apply(this, arguments);
            this._innerHtml = null;
        },
        _render: function () {
            if (!this._innerHtml)
                this._innerHtml = this.$el.html();
            var value = this.value || 0;
            var result = '';
            for(var i=0; i < value; i++)
                result += this._innerHtml;
            this.$el.html(result);
        }
    });

    registry.add('rating', FieldRating);
});
