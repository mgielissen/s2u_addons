from odoo import api, models


class PrintPalletsSaldo(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_pallets_saldo'

    @api.model
    def get_report_values(self, docids, data=None):

        def keyindict(key_search, dict):
            for key, value in sorted(iter(dict.items())):
                if key == key_search:
                    return value
            return False

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        correction_obj = self.env['s2u.warehouse.pallet.correction']
        retourn_obj = self.env['s2u.warehouse.incoming.pallet.retour']

        transfers = trans_obj.search(['|', ('incoming_id', '!=', False), ('outgoing_id', '!=', False),
                                      ('transaction_date', '<=', data['form']['date_till']),
                                      ('item_picking', '=', False),
                                      ('count_unit', '=', True)])
        correctings = correction_obj.search([('entry_date', '<=', data['form']['date_till'])], order='entity_id')
        retourns = retourn_obj.search([('date_delivery', '<=', data['form']['date_till'])])

        customer_list = {}
        trans_unit_ids_in = []
        trans_unit_ids_out = []
        for correcting in correctings:
            if not keyindict(correcting.entity_id.name, customer_list):
                customer_list[correcting.entity_id.name] = {'pallet': {}}
            if not keyindict(correcting.pallet_id.full_name, customer_list[correcting.entity_id.name]['pallet']):
                customer_list[correcting.entity_id.name]['pallet'][correcting.pallet_id.full_name] = 0
            customer_list[correcting.entity_id.name]['pallet'][correcting.pallet_id.full_name] += correcting.pallets
        for transfer in transfers:
            if transfer.unit_id.type == 'pallet' and transfer.outgoing_id and transfer.unit_id.id not in trans_unit_ids_out:
                trans_unit_ids_out.append(transfer.unit_id.id)
                if not keyindict(transfer.outgoing_id.entity_id.name, customer_list):
                    customer_list[transfer.outgoing_id.entity_id.name] = {'pallet': {}}
                if not keyindict(transfer.unit_id.pallet_id.full_name, customer_list[transfer.outgoing_id.entity_id.name]['pallet']):
                    customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name] = 0
                customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name] += (1 * transfer.unit_id.pallet_factor)
            if transfer.unit_id.type == 'pallet' and transfer.incoming_id and transfer.unit_id.id not in trans_unit_ids_in :
                trans_unit_ids_in.append(transfer.unit_id.id)
                if not keyindict(transfer.incoming_id.entity_id.name, customer_list):
                    customer_list[transfer.incoming_id.entity_id.name] = {'pallet': {}}
                if not keyindict(transfer.unit_id.pallet_id.full_name, customer_list[transfer.incoming_id.entity_id.name]['pallet']):
                    customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name] = 0
                customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name] -= (1 * transfer.unit_id.pallet_factor)
            if transfer.unit_id.type != 'pallet' and transfer.parent_id:
                if transfer.parent_id.type == 'pallet' and transfer.outgoing_id and transfer.parent_id.id not in trans_unit_ids_out:
                    trans_unit_ids_out.append(transfer.parent_id.id)
                    if not keyindict(transfer.outgoing_id.entity_id.name, customer_list):
                        customer_list[transfer.outgoing_id.entity_id.name] = {'pallet': {}}
                    if not keyindict(transfer.parent_id.pallet_id.full_name, customer_list[transfer.outgoing_id.entity_id.name]['pallet']):
                        customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name] = 0
                    customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name] += (1 * transfer.parent_id.pallet_factor)
                if transfer.parent_id.type == 'pallet' and transfer.incoming_id and transfer.parent_id.id not in trans_unit_ids_in :
                    trans_unit_ids_in.append(transfer.parent_id.id)
                    if not keyindict(transfer.incoming_id.entity_id.name, customer_list):
                        customer_list[transfer.incoming_id.entity_id.name] = {'pallet': {}}
                    if not keyindict(transfer.parent_id.pallet_id.full_name, customer_list[transfer.incoming_id.entity_id.name]['pallet']):
                        customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name] = 0
                    customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name] -= (1 * transfer.parent_id.pallet_factor)
        for retour in retourns:
            if not keyindict(retour.incoming_id.entity_id.name, customer_list):
                 customer_list[retour.incoming_id.entity_id.name] = {'pallet': {}}
            if not keyindict(retour.pallet_id.full_name, customer_list[retour.incoming_id.entity_id.name]['pallet']):
                 customer_list[retour.incoming_id.entity_id.name]['pallet'][retour.pallet_id.full_name] = 0
            customer_list[retour.incoming_id.entity_id.name]['pallet'][retour.pallet_id.full_name] += retour.pallet_qty

        list_customer = []
        for key, value in sorted(iter(customer_list.items())):
            location = []
            gesamt = 0.00
            for key2, value2 in iter(value['pallet'].items()):
                temp = {
                    'customer': key,
                    'pallet': key2,
                    'qty': value2
                }
                location.append(temp)
                gesamt += value2
            temp = {
                'customer': key,
                'pallets': location,
                'gesamt': gesamt
            }
            list_customer.append(temp)

        return {
            'customers': list_customer,
            'date_till': data['form']['date_till']
        }

