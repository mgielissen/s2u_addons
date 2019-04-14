from datetime import datetime

from odoo import api, models


class PrintPalletsHistory(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_pallets_history'

    @api.model
    def get_report_values(self, docids, data=None):

        def keyindict(key_search, dict):
            for key, value in sorted(iter(dict.items())):
                if key == key_search:
                    return value
            return False

        correction_obj = self.env['s2u.warehouse.pallet.correction']        
        retourn_obj = self.env['s2u.warehouse.incoming.pallet.retour']
        trans_obj = self.env['s2u.warehouse.unit.product.transaction']

        transfers = trans_obj.search(['|', ('incoming_id', '!=', False), ('outgoing_id', '!=', False),
                                      ('count_unit', '=', True), ('item_picking', '=', False),
                                      ('transaction_date', '<=', data['form']['date_till']),
                                      ('entity_id', '=', data['form']['entity_id'][0])])
        correctings = correction_obj.search([('entry_date', '<=', data['form']['date_till']),
                                             ('entity_id', '=', data['form']['entity_id'][0])], order='entity_id')

        retouren = retourn_obj.search([('date_delivery', '<=', data['form']['date_till'])])
        trans_unit_ids_in = []
        trans_unit_ids_out = []
        history_list = {}
        key_id = []
        key_date = {}
        for correcting in correctings:
            key_name = '%s#%s' % ('Correction', correcting.id)
            if not keyindict(key_name, history_list):
                if key_name not in key_id:
                    key_id.append(key_name)
                    key_date[key_name] = correcting.entry_date
                history_list[key_name] = {'no': key_name,
                                          'type': 'c',
                                          'date': datetime.strptime(correcting.entry_date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                                          'note': correcting.note,
                                          'external': '',
                                          'palleten_keys': [],
                                          'palleten': {}}
            if not keyindict(correcting.pallet_id.full_name, history_list[key_name]['palleten']):
                history_list[key_name]['palleten'][correcting.pallet_id.full_name] = correcting.pallets
            if correcting.pallet_id.full_name not in history_list[key_name]['palleten_keys']:
                history_list[key_name]['palleten_keys'].append(correcting.pallet_id.full_name)
        for transfer in transfers:
            if transfer.unit_id.type == 'pallet' and not transfer.outgoing_id and transfer.unit_id.id not in trans_unit_ids_in :
                trans_unit_ids_in.append(transfer.unit_id.id)
                if not transfer.supplier_no:
                    key_name = '%s %s %s' % ('Incoming', transfer.incoming_id.name, transfer.transaction_date)
                else:
                    key_name = '%s %s %s (%s)' % ('Incoming', transfer.incoming_id.name, transfer.transaction_date, transfer.supplier_no)
                if not keyindict(key_name, history_list):
                    if key_name not in key_id:
                        key_id.append(key_name)
                        key_date[key_name] = transfer.transaction_date
                    history_list[key_name] = {'no': key_name,
                                              'type': 'i',
                                              'date': datetime.strptime(transfer.transaction_date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                                              'note': '',
                                              'palleten_keys': [],
                                              'palleten': {}}
                if not keyindict(transfer.unit_id.pallet_id.full_name, history_list[key_name]['palleten']):
                    history_list[key_name]['palleten'][transfer.unit_id.pallet_id.full_name] = 0
                history_list[key_name]['palleten'][transfer.unit_id.pallet_id.full_name] += 1 * transfer.unit_id.pallet_factor

                if transfer.unit_id.pallet_id.full_name not in history_list[key_name]['palleten_keys']:
                    history_list[key_name]['palleten_keys'].append(transfer.unit_id.pallet_id.full_name)
            if transfer.unit_id.type == 'pallet' and not transfer.incoming_id and transfer.unit_id.id not in trans_unit_ids_out:
                trans_unit_ids_out.append(transfer.unit_id.id)
                key_name = '%s %s' % ('Outgoing', transfer.outgoing_id.name)
                if not keyindict(key_name, history_list):
                    if key_name not in key_id:
                        key_id.append(key_name)
                        key_date[key_name] = transfer.outgoing_id.transaction_date
                    history_list[key_name] = {'no': key_name,
                                              'type': 'o',
                                              'date': datetime.strptime(transfer.outgoing_id.transaction_date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                                              'note': '',
                                              'external': '',
                                              'palleten_keys': [],
                                              'palleten': {}}
                if not keyindict(transfer.unit_id.pallet_id.full_name, history_list[key_name]['palleten']):
                    history_list[key_name]['palleten'][transfer.unit_id.pallet_id.full_name] = 0
                history_list[key_name]['palleten'][transfer.unit_id.pallet_id.full_name] += 1 * transfer.unit_id.pallet_factor
                if transfer.unit_id.pallet_id.full_name not in history_list[key_name]['palleten_keys']:
                    history_list[key_name]['palleten_keys'].append(transfer.unit_id.pallet_id.full_name)
            if transfer.unit_id.type != 'pallet' and transfer.parent_id:
                if transfer.outgoing_id and transfer.parent_id.type == 'pallet' and transfer.parent_id.id not in trans_unit_ids_out:
                    trans_unit_ids_out.append(transfer.parent_id.id)
                    key_name = '%s %s' % ('Outgoing', transfer.outgoing_id.name)
                    if not keyindict(key_name, history_list):
                        if key_name not in key_id:
                            key_id.append(key_name)
                            key_date[key_name] = transfer.outgoing_id.transaction_date
                        history_list[key_name] = {'no': key_name,
                                                   'type': 'o',
                                                   'date': datetime.strptime(transfer.outgoing_id.transaction_date,
                                                   '%Y-%m-%d').strftime('%d.%m.%Y'),
                                                   'note': '',
                                                   'external': '',
                                                   'palleten_keys': [],
                                                   'palleten': {}}
                    if not keyindict(transfer.parent_id.pallet_id.full_name, history_list[key_name]['palleten']):
                        history_list[key_name]['palleten'][transfer.parent_id.pallet_id.full_name] = 0
                    history_list[key_name]['palleten'][transfer.parent_id.pallet_id.full_name] += 1 * transfer.parent_id.pallet_factor
                    if transfer.parent_id.pallet_id.full_name not in history_list[key_name]['palleten_keys']:
                        history_list[key_name]['palleten_keys'].append(transfer.parent_id.pallet_id.full_name)
                if transfer.incoming_id and transfer.parent_id.type == 'pallet' and transfer.parent_id.id not in trans_unit_ids_in:
                    trans_unit_ids_in.append(transfer.parent_id.id)
                    if not transfer.supplier_no:
                        key_name = '%s %s %s' % ('Incoming', transfer.incoming_id.name, transfer.transaction_date)
                    else:
                        key_name = '%s %s %s (%s)' % (
                        'Incoming', transfer.incoming_id.name, transfer.transaction_date, transfer.supplier_no)
                    if not keyindict(key_name, history_list):
                        if key_name not in key_id:
                            key_id.append(key_name)
                            key_date[key_name] = transfer.transaction_date
                        history_list[key_name] = {'no': key_name,
                                                  'type': 'i',
                                                  'date': datetime.strptime(transfer.transaction_date, '%Y-%m-%d').strftime(
                                                  '%d.%m.%Y'),
                                                  'note': '',
                                                  'palleten_keys': [],
                                                  'palleten': {}}
                    if not keyindict(transfer.parent_id.pallet_id.full_name, history_list[key_name]['palleten']):
                        history_list[key_name]['palleten'][transfer.parent_id.pallet_id.full_name] = 0
                    history_list[key_name]['palleten'][
                        transfer.parent_id.pallet_id.full_name] += 1 * transfer.parent_id.pallet_factor

                    if transfer.parent_id.pallet_id.full_name not in history_list[key_name]['palleten_keys']:
                        history_list[key_name]['palleten_keys'].append(transfer.parent_id.pallet_id.full_name)
        for retour in retouren:
            if retour.incoming_id.entity_id.id == data['form']['entity_id'][0]:
                key_name = '%s %s %s' % ('Incoming', retour.incoming_id.name, retour.date_delivery)
                if not keyindict(key_name, history_list):
                    if key_name not in key_id:
                        key_id.append(key_name)
                        key_date[key_name] = retour.date_delivery
                    history_list[key_name] = {'no': key_name,
                                              'type': 'i',
                                              'date': datetime.strptime(retour.date_delivery, '%Y-%m-%d').strftime(
                                                  '%d.%m.%Y'),
                                              'note': '',
                                              'palleten_keys': [],
                                              'palleten': {}}
                if not keyindict(retour.pallet_id.full_name, history_list[key_name]['palleten']):
                    history_list[key_name]['palleten'][retour.pallet_id.full_name] = 0
                history_list[key_name]['palleten'][retour.pallet_id.full_name] -= retour.pallet_qty
                if retour.pallet_id.full_name not in history_list[key_name]['palleten_keys']:
                    history_list[key_name]['palleten_keys'].append(retour.pallet_id.full_name)

        list_history = []
        for key in sorted(key_date, key=key_date.__getitem__):
            paletten = []
            temp_p = {}
            temp_p['number'] = history_list[key]['no']
            temp_p['date'] = history_list[key]['date']
            temp_p['type'] = history_list[key]['type']
            temp_p['note'] = history_list[key]['note']
            for keys in sorted(history_list[key]['palleten_keys']):
                temp_l = {}
                temp_l['number'] = history_list[key]['no']
                temp_l['pallet'] = keys
                temp_l['qty'] = history_list[key]['palleten'][keys]
                paletten.append(temp_l)
            temp_p['pallets'] = paletten
            list_history.append(temp_p)

        return {
            'historys': list_history,
            'customer': data['form']['entity_id'][1],
            'date_till': data['form']['date_till']
        }

