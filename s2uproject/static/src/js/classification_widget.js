odoo.define('classification_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var registry = require('web.field_registry')

    var FieldClassification = AbstractField.extend({
        template: 'FieldProjectClassification',

        init: function() {
            this._super.apply(this, arguments);
        },
        _render: function () {
            var value = this.value || '';
            var result = '';
            if (value.indexOf('h') > -1) {
                result += '<img border="0" draggable="false" height="60" width="60" src="s2uproject/static/src/img/project_shae.png">';
            }
            if (value.indexOf('b') > -1) {
                result += '<img border="0" draggable="false" height="60" width="60" src="s2uproject/static/src/img/project_brons.png">';
            }
            if (value.indexOf('s') > -1) {
                result += '<img border="0" draggable="false" height="60" width="60" src="s2uproject/static/src/img/project_silver.png">';
            }
            if (value.indexOf('g') > -1) {
                result += '<img border="0" draggable="false" height="60" width="60" src="s2uproject/static/src/img/project_gold.png">';
            }
            if (value.indexOf('p') > -1) {
                result += '<img border="0" draggable="false" height="60" width="60" src="s2uproject/static/src/img/project_platinum.png">';
            }
            this.$el.html(result);
        }
    });

    var FieldClassificationKanban = AbstractField.extend({
        template: 'FieldProjectClassificationKanban',

        init: function() {
            this._super.apply(this, arguments);
        },
        _render: function () {
            var value = this.value || '';
            var result = '';
            if (value.indexOf('h') > -1) {
                result += '<img border="0" draggable="false" height="30" width="30" src="s2uproject/static/src/img/project_shae.png">';
            }
            if (value.indexOf('b') > -1) {
                result += '<img border="0" draggable="false" height="30" width="30" src="s2uproject/static/src/img/project_brons.png">';
            }
            if (value.indexOf('s') > -1) {
                result += '<img border="0" draggable="false" height="30" width="30" src="s2uproject/static/src/img/project_silver.png">';
            }
            if (value.indexOf('g') > -1) {
                result += '<img border="0" draggable="false" height="30" width="30" src="s2uproject/static/src/img/project_gold.png">';
            }
            if (value.indexOf('p') > -1) {
                result += '<img border="0" draggable="false" height="30" width="30" src="s2uproject/static/src/img/project_platinum.png">';
            }
            this.$el.html(result);
        }
    });

    registry.add('classification', FieldClassification);
    registry.add('classification_kanban', FieldClassificationKanban);
});
