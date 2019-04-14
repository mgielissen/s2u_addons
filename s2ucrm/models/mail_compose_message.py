from odoo import _, api, fields, models, SUPERUSER_ID, tools


class MailComposer(models.TransientModel):

    _inherit = 'mail.compose.message'

    @api.multi
    def get_mail_values(self, res_ids):
        self.ensure_one()

        res = super(MailComposer, self).get_mail_values(res_ids)

        try:
            if self.reply_to:
                for res_id in res_ids:
                    res[res_id]['reply_to'] = self.reply_to
                    print('yes')
        except:
            pass

        return res